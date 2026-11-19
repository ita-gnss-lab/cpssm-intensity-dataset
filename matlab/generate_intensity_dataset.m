function generate_intensity_dataset(output_directory, simulator_directory, ...
    duration_seconds, sampling_period_seconds, seeds, spectral_parameters, ...
    rhof_veff_seconds, band_names, band_frequencies_hz)
% Generate jointly coupled GPS L1/L2/L5 CPSSM intensities.
%
% spectral_parameters = [U, mu0, p1, p2] defines the L1 spectrum. The
% simulator's native extrapolation supplies the corresponding L2/L5 spectra.

    arguments
        output_directory (1,1) string
        simulator_directory (1,1) string
        duration_seconds (1,1) double {mustBePositive}
        sampling_period_seconds (1,1) double {mustBePositive}
        seeds (1,:) double {mustBeInteger, mustBeNonnegative}
        spectral_parameters (1,4) double {mustBePositive}
        rhof_veff_seconds (1,1) double {mustBePositive}
        band_names (1,1) string
        band_frequencies_hz (1,:) double {mustBePositive}
    end
    bands = split(band_names, ',').';
    if numel(bands) ~= 3 || numel(band_frequencies_hz) ~= 3
        error('Exactly three bands and frequencies are required.');
    end
    addpath(genpath(fullfile(simulator_directory, 'libs')));
    if ~isfolder(output_directory)
        mkdir(output_directory);
    end

    sim_params = get_const_sim_params();
    sim_params.sim_time = duration_seconds;
    sim_params.t_samp = sampling_period_seconds;
    sim_params.severity = 'strong';
    sim_params.temporal_support = seconds( ...
        0:sampling_period_seconds:duration_seconds);
    sim_params.const.spectral.strong.U_ref = spectral_parameters(1);
    sim_params.const.spectral.strong.mu0_ref = spectral_parameters(2);
    sim_params.const.spectral.strong.p1 = spectral_parameters(3);
    sim_params.const.spectral.strong.p2 = spectral_parameters(4);

    nfft = nicefftnum(duration_seconds / sampling_period_seconds + 1);
    output.doppler_frequency_support = ...
        (-nfft/2:nfft/2-1) / (nfft * sampling_period_seconds);
    for band_index = 1:numel(bands)
        output.gps.spectral.(bands(band_index)) = extrapolate_spectral_params( ...
            sim_params, band_frequencies_hz(band_index));
    end

    sample_count = round(duration_seconds / sampling_period_seconds);
    total_start = tic;
    for seed_index = 1:numel(seeds)
        seed = seeds(seed_index);
        % Match the seed accepted by the public cpssm wrapper, which advances
        % it once before synthesizing its first satellite realization.
        sim_params.seed = seed + 1;
        intensity = zeros(sample_count, numel(bands));
        for band_index = 1:numel(bands)
            scale = extrapolate_scaling_param(sim_params, ...
                band_frequencies_hz(band_index), rhof_veff_seconds);
            [~, ~, ~, ~, amplitude, ~] = get_scintillation_realization( ...
                sim_params, output, 'gps', bands(band_index), scale, nfft);
            values = double(amplitude{1:sample_count, :});
            intensity(:, band_index) = values.^2;
        end

        values = [(0:sample_count-1).', intensity];
        filename = fullfile(output_directory, sprintf('seed_%d.csv', seed));
        file_id = fopen(filename, 'w');
        if file_id < 0
            error('Could not open %s', filename);
        end
        cleanup = onCleanup(@() fclose(file_id));
        fprintf(file_id, 'sample,L1_intensity,L2_intensity,L5_intensity\n');
        fprintf(file_id, '%.0f,%.17g,%.17g,%.17g\n', values.');
        clear cleanup

        elapsed = toc(total_start);
        eta = elapsed * (numel(seeds) - seed_index) / seed_index;
        fprintf(['Completed seed %d (%d/%d); elapsed %.1f s, ' ...
            'ETA %.1f s\n'], seed, seed_index, numel(seeds), elapsed, eta);
    end
end

