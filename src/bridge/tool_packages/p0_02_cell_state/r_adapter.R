#!/usr/bin/env Rscript

ADAPTER_IMPLEMENTATION_VERSION <- "0.1.2"

stop_bridge <- function(code, detail = NULL) {
    msg <- if (is.null(detail)) code else paste0(code, ": ", detail)
    stop(msg, call. = FALSE)
}

`%||%` <- function(x, y) if (is.null(x)) y else x

require_packages <- function(packages) {
    missing <- packages[!vapply(packages, requireNamespace, logical(1), quietly = TRUE)]
    if (length(missing)) stop_bridge("r_package_missing", paste(missing, collapse = ","))
}

parse_args <- function(args) {
    if (!length(args) || !args[[1]] %in% c("singler", "scmap", "symphony", "scconform")) {
        stop_bridge("method_required", "singler|scmap|symphony|scconform")
    }
    out <- list(method = args[[1]])
    rest <- args[-1]
    if (length(rest) %% 2L) stop_bridge("arguments_must_be_flag_value_pairs")
    for (i in seq(1L, length(rest), by = 2L)) {
        key <- rest[[i]]
        if (!startsWith(key, "--")) stop_bridge("argument_flag_invalid", key)
        out[[gsub("-", "_", substring(key, 3L))]] <- rest[[i + 1L]]
    }
    out
}

required_arg <- function(args, name) {
    value <- args[[name]]
    if (is.null(value) || !nzchar(value)) stop_bridge("argument_required", name)
    value
}

safe_name <- function(value) {
    if (!is.character(value) || length(value) != 1L || !nzchar(value) ||
        basename(value) != value || grepl("[/\\\\]", value) || value %in% c(".", "..")) {
        stop_bridge("bundle_artifact_path_invalid", value)
    }
    value
}

sha256 <- function(path) digest::digest(path, algo = "sha256", file = TRUE)

validate_artifact <- function(root, name, expected) {
    name <- safe_name(name)
    path <- file.path(root, name)
    if (!file.exists(path)) stop_bridge("bundle_artifact_missing", name)
    if (is.null(expected) || !identical(tolower(sha256(path)), tolower(expected))) {
        stop_bridge("bundle_artifact_checksum_mismatch", name)
    }
    path
}

read_table <- function(path) {
    if (grepl("\\.parquet$", path, ignore.case = TRUE)) {
        require_packages("arrow")
        return(as.data.frame(arrow::read_parquet(path), stringsAsFactors = FALSE))
    }
    read.delim(path, check.names = FALSE, stringsAsFactors = FALSE)
}

read_sparse_h5 <- function(path) {
    require_packages(c("rhdf5", "Matrix"))
    shape <- as.integer(rhdf5::h5read(path, "matrix/shape"))
    data <- as.numeric(rhdf5::h5read(path, "matrix/data"))
    indices <- as.integer(rhdf5::h5read(path, "matrix/indices"))
    indptr <- as.integer(rhdf5::h5read(path, "matrix/indptr"))
    if (length(shape) != 2L || length(indptr) != shape[[1]] + 1L ||
        length(indices) != length(data)) stop_bridge("bundle_matrix_invalid")
    transposed <- Matrix::sparseMatrix(
        i = indices + 1L, p = indptr, x = data,
        dims = rev(shape), giveCsparse = TRUE
    )
    methods::as(Matrix::t(transposed), "CsparseMatrix")
}

normalize_expression <- function(matrix, semantics) {
    if (identical(semantics, "normalized_expression")) return(matrix)
    if (!identical(semantics, "raw_counts")) {
        stop_bridge("bundle_matrix_semantics_unsupported", semantics)
    }
    if (any(matrix@x < 0) || any(abs(matrix@x - round(matrix@x)) > 1e-6)) {
        stop_bridge("raw_counts_must_be_nonnegative_integers")
    }
    totals <- Matrix::rowSums(matrix)
    scale <- ifelse(totals > 0, 10000 / totals, 0)
    normalized <- Matrix::Diagonal(x = scale) %*% matrix
    normalized@x <- log1p(normalized@x)
    methods::as(normalized, "CsparseMatrix")
}

read_bundle <- function(exchange_root, asset_id) {
    require_packages(c("jsonlite", "digest", "Matrix"))
    root <- file.path(exchange_root, asset_id)
    manifest_path <- file.path(root, "bundle.json")
    if (!file.exists(manifest_path)) stop_bridge("bundle_manifest_invalid", asset_id)
    manifest <- jsonlite::fromJSON(manifest_path, simplifyVector = TRUE)
    if (!identical(manifest$asset_id, asset_id)) stop_bridge("bundle_asset_id_mismatch", asset_id)
    if (is.null(manifest$source_family_id) || is.null(manifest$label_level)) {
        stop_bridge("bundle_context_incomplete", asset_id)
    }
    artifacts <- manifest$artifacts
    required <- c("matrix.h5", "features.tsv", "observations.tsv", "observations.parquet")
    for (name in required) validate_artifact(root, name, artifacts[[name]])
    matrix <- read_sparse_h5(file.path(root, "matrix.h5"))
    matrix <- normalize_expression(matrix, manifest$matrix_semantics)
    features <- read.delim(
        file.path(root, "features.tsv"), header = FALSE, stringsAsFactors = FALSE
    )[[1]]
    observations <- read.delim(
        file.path(root, "observations.tsv"), check.names = FALSE, stringsAsFactors = FALSE
    )
    needed <- c("observation_id", "sample_id", "true_label")
    if (!all(needed %in% names(observations))) stop_bridge("bundle_observations_incomplete")
    if (anyDuplicated(observations$observation_id)) stop_bridge("bundle_observation_ids_not_unique")
    if (anyDuplicated(features)) stop_bridge("bundle_features_not_unique")
    expected <- as.integer(unlist(manifest$matrix_shape))
    if (!identical(dim(matrix), c(nrow(observations), length(features))) ||
        !identical(dim(matrix), expected)) stop_bridge("bundle_matrix_shape_mismatch")
    list(matrix = matrix, features = features, observations = observations, manifest = manifest)
}

read_split <- function(path, asset_id, observations) {
    require_packages("jsonlite")
    split <- jsonlite::fromJSON(path, simplifyVector = TRUE)
    if (!identical(split$phase, "pilot") || isTRUE(split$locked_assets_opened) ||
        isTRUE(split$sealed_assets_opened)) stop_bridge("locked_or_sealed_split_forbidden")
    records <- split$records
    if (!is.data.frame(records)) records <- as.data.frame(records, stringsAsFactors = FALSE)
    records <- records[records$asset_id == asset_id, , drop = FALSE]
    if (!nrow(records)) stop_bridge("asset_not_in_split_manifest", asset_id)
    roles <- tolower(records$data_role)
    if (any(records$partition == "locked_test") || any(grepl("sealed|competitor", roles))) {
        stop_bridge("locked_or_sealed_split_forbidden", asset_id)
    }
    fold_ids <- sort(unique(records$fold_id[!is.na(records$fold_id) & nzchar(records$fold_id)]))
    if (!length(fold_ids)) stop_bridge("benchmark_folds_not_found", asset_id)
    folds <- list()
    for (fold_id in fold_ids) {
        current <- records[records$fold_id == fold_id, , drop = FALSE]
        if (anyDuplicated(current$sample_id)) stop_bridge("split_sample_leakage", fold_id)
        partition <- current$partition[match(observations$sample_id, current$sample_id)]
        if (anyNA(partition)) stop_bridge("split_missing_bundle_sample", fold_id)
        if (!all(c("train", "calibration", "test") %in% partition)) {
            stop_bridge("train_calibration_test_required", fold_id)
        }
        folds[[fold_id]] <- partition
    }
    folds
}

validate_training <- function(observations, partition, fold_id) {
    labels <- observations$true_label[partition == "train"]
    if (anyNA(labels) || any(!nzchar(labels))) stop_bridge("training_labels_missing", fold_id)
    if (length(unique(labels)) < 2L) stop_bridge("at_least_two_training_labels_required", fold_id)
}

prediction_rows <- function(fold_id, observations, partition, predicted, score, margin, manifest) {
    keep <- partition %in% c("calibration", "test")
    labels <- as.character(predicted)
    sets <- vapply(labels, function(x) {
        if (is.na(x) || x == "unassigned") "[]" else jsonlite::toJSON(c(x), auto_unbox = FALSE)
    }, character(1))
    data.frame(
        fold_id = fold_id,
        observation_id = observations$observation_id[keep],
        sample_id = observations$sample_id[keep],
        asset_id = manifest$asset_id,
        source_family_id = manifest$source_family_id,
        label_level = manifest$label_level,
        partition = partition[keep],
        true_label = observations$true_label[keep],
        predicted_label = labels,
        score = as.numeric(score),
        margin = as.numeric(margin),
        assignment_state = ifelse(labels == "unassigned", "unknown_uncalibrated", "assigned_uncalibrated"),
        prediction_set = sets,
        check.names = FALSE,
        stringsAsFactors = FALSE
    )
}

run_singler <- function(bundle, folds) {
    require_packages(c("SingleR", "jsonlite"))
    out <- list()
    for (fold_id in names(folds)) {
        partition <- folds[[fold_id]]
        validate_training(bundle$observations, partition, fold_id)
        train <- partition == "train"
        query <- partition %in% c("calibration", "test")
        ref <- Matrix::t(bundle$matrix[train, , drop = FALSE])
        test <- Matrix::t(bundle$matrix[query, , drop = FALSE])
        rownames(ref) <- rownames(test) <- bundle$features
        trained <- SingleR::trainSingleR(ref, bundle$observations$true_label[train])
        result <- SingleR::classifySingleR(test, trained)
        scores <- as.matrix(result$scores)
        labels <- as.character(result$labels)
        top <- scores[cbind(seq_len(nrow(scores)), match(labels, colnames(scores)))]
        out[[fold_id]] <- prediction_rows(
            fold_id, bundle$observations, partition, labels, top, result$delta.next,
            bundle$manifest
        )
    }
    do.call(rbind, out)
}

make_sce <- function(bundle, rows, labels = NULL) {
    assays <- list(logcounts = Matrix::t(bundle$matrix[rows, , drop = FALSE]))
    meta <- S4Vectors::DataFrame(row.names = bundle$observations$observation_id[rows])
    if (!is.null(labels)) meta$cell_type1 <- labels
    sce <- SingleCellExperiment::SingleCellExperiment(assays = assays, colData = meta)
    SummarizedExperiment::rowData(sce)$feature_symbol <- bundle$features
    sce
}

run_scmap <- function(bundle, folds) {
    require_packages(c("scmap", "SingleCellExperiment", "SummarizedExperiment", "S4Vectors", "jsonlite"))
    out <- list()
    for (fold_id in names(folds)) {
        partition <- folds[[fold_id]]
        validate_training(bundle$observations, partition, fold_id)
        train <- partition == "train"
        query <- partition %in% c("calibration", "test")
        ref <- make_sce(bundle, train, bundle$observations$true_label[train])
        ref <- scmap::selectFeatures(
            ref, n_features = min(500L, nrow(ref)), suppress_plot = TRUE
        )
        ref <- scmap::indexCluster(
            ref[SummarizedExperiment::rowData(ref)$scmap_features, ], cluster_col = "cell_type1"
        )
        projected <- scmap::scmapCluster(
            make_sce(bundle, query),
            index_list = list(reference = S4Vectors::metadata(ref)$scmap_cluster_index),
            threshold = 0
        )
        labels <- as.character(projected$combined_labs)
        score <- as.numeric(projected$scmap_cluster_siml[, 1])
        out[[fold_id]] <- prediction_rows(
            fold_id, bundle$observations, partition, labels, score,
            rep(NA_real_, length(score)), bundle$manifest
        )
    }
    do.call(rbind, out)
}

run_symphony <- function(bundle, folds, seed) {
    require_packages(c("symphony", "jsonlite"))
    out <- list()
    for (fold_id in names(folds)) {
        partition <- folds[[fold_id]]
        validate_training(bundle$observations, partition, fold_id)
        train <- partition == "train"
        query <- partition %in% c("calibration", "test")
        ref_exp <- Matrix::t(bundle$matrix[train, , drop = FALSE])
        query_exp <- Matrix::t(bundle$matrix[query, , drop = FALSE])
        rownames(ref_exp) <- rownames(query_exp) <- bundle$features
        colnames(ref_exp) <- bundle$observations$observation_id[train]
        colnames(query_exp) <- bundle$observations$observation_id[query]
        ref_meta <- data.frame(
            sample_id = bundle$observations$sample_id[train],
            cell_type = bundle$observations$true_label[train],
            row.names = colnames(ref_exp), stringsAsFactors = FALSE
        )
        query_meta <- data.frame(
            sample_id = bundle$observations$sample_id[query],
            row.names = colnames(query_exp), stringsAsFactors = FALSE
        )
        dims <- min(20L, ncol(ref_exp) - 1L, nrow(ref_exp) - 1L)
        if (dims < 2L) stop_bridge("symphony_training_matrix_too_small", fold_id)
        batch_var <- if (length(unique(ref_meta$sample_id)) > 1L) "sample_id" else NULL
        reference <- symphony::buildReference(
            ref_exp, ref_meta, vars = batch_var,
            K = min(100L, max(2L, floor(sqrt(ncol(ref_exp))))),
            verbose = FALSE, do_umap = FALSE, do_normalize = FALSE,
            vargenes_groups = batch_var, topn = min(2000L, nrow(ref_exp)),
            d = dims, seed = seed
        )
        mapped <- symphony::mapQuery(
            query_exp, query_meta, reference, vars = NULL,
            do_normalize = FALSE, do_umap = FALSE
        )
        mapped <- symphony::knnPredict(
            mapped, reference, ref_meta$cell_type,
            k = min(5L, nrow(ref_meta)), save_as = "bridge_prediction",
            confidence = TRUE, seed = seed
        )
        labels <- as.character(mapped$meta_data$bridge_prediction)
        score <- as.numeric(mapped$meta_data$bridge_prediction_prob)
        out[[fold_id]] <- prediction_rows(
            fold_id, bundle$observations, partition, labels, score,
            rep(NA_real_, length(score)), bundle$manifest
        )
    }
    do.call(rbind, out)
}

run_scconform <- function(args) {
    require_packages(c("scConform", "jsonlite"))
    input <- required_arg(args, "predictions")
    metadata_path <- args$probability_metadata %||% paste0(input, ".metadata.json")
    if (!file.exists(metadata_path)) stop_bridge("probability_metadata_missing")
    metadata <- jsonlite::fromJSON(metadata_path, simplifyVector = TRUE)
    if (!identical(metadata$probability_semantics, "categorical_simplex") ||
        !isTRUE(metadata$conformal_eligible)) stop_bridge("probability_semantics_not_conformal_ready")
    frame <- read_table(input)
    required <- c("fold_id", "observation_id", "partition", "true_label", "predicted_label", "score", "margin")
    if (!all(required %in% names(frame))) stop_bridge("prediction_contract_incomplete")
    if (anyNA(frame$fold_id) || anyNA(frame$observation_id) ||
        anyDuplicated(frame[c("fold_id", "observation_id")])) {
        stop_bridge("prediction_identity_not_unique")
    }
    probability_names <- grep("^prob__", names(frame), value = TRUE)
    if (length(probability_names) < 2L) stop_bridge("probability_columns_required")
    probabilities <- as.matrix(data.frame(lapply(frame[probability_names], as.numeric), check.names = FALSE))
    colnames(probabilities) <- substring(probability_names, 7L)
    if (anyNA(probabilities) || any(probabilities < 0 | probabilities > 1) ||
        any(abs(rowSums(probabilities) - 1) > 1e-5)) stop_bridge("probability_rows_must_sum_to_one")
    alpha <- as.numeric(args$alpha %||% "0.1")
    if (!is.finite(alpha) || alpha <= 0 || alpha >= 1) stop_bridge("alpha_invalid")
    out <- list()
    for (fold_id in sort(unique(frame$fold_id))) {
        current <- frame$fold_id == fold_id
        cal <- current & frame$partition == "calibration"
        test <- current & frame$partition == "test"
        if (!any(cal) || !any(test)) stop_bridge("independent_calibration_and_test_required", fold_id)
        if (length(intersect(frame$observation_id[cal], frame$observation_id[test]))) {
            stop_bridge("calibration_test_overlap", fold_id)
        }
        y_cal <- as.character(frame$true_label[cal])
        if (anyNA(y_cal) || any(!y_cal %in% colnames(probabilities))) {
            stop_bridge("calibration_labels_invalid", fold_id)
        }
        sets <- scConform::getPredictionSets(
            x_query = probabilities[test, , drop = FALSE],
            x_cal = probabilities[cal, , drop = FALSE],
            y_cal = y_cal,
            onto = NULL, alpha = alpha, follow_ontology = FALSE,
            resample = FALSE, labels = colnames(probabilities), return_sc = FALSE
        )
        selected <- frame[test, , drop = FALSE]
        selected$prediction_set <- vapply(
            sets, jsonlite::toJSON, character(1), auto_unbox = FALSE
        )
        selected$assignment_state <- vapply(sets, function(x) {
            if (!length(x)) "conformal_empty" else if (length(x) == 1L) "conformal_singleton" else "conformal_set"
        }, character(1))
        out[[fold_id]] <- selected
    }
    result <- do.call(rbind, out)
    attr(result, "metadata") <- list(
        adapter = "scconform_calibration",
        adapter_implementation_version = ADAPTER_IMPLEMENTATION_VERSION,
        package_version = as.character(utils::packageVersion("scConform")),
        probability_semantics = "prediction_set",
        base_adapter = metadata$adapter,
        query_expression_used_as_unlabeled_during_training = isTRUE(
            metadata$query_expression_used_as_unlabeled_during_training
        ),
        alpha = alpha,
        independent_evidence_vote = FALSE,
        evidence_family = metadata$evidence_family,
        calibration_partition_required = TRUE,
        base_prediction_sha256 = sha256(input),
        probability_metadata_sha256 = sha256(metadata_path),
        split_manifest_sha256 = metadata$split_manifest_sha256,
        split_manifest_id = metadata$split_manifest_id,
        benchmark_spec_ref = metadata$benchmark_spec_ref,
        input_bundle_sha256 = metadata$input_bundle_sha256
    )
    result
}

method_metadata <- function(method, seed) {
    package <- switch(method, singler = "SingleR", scmap = "scmap", symphony = "symphony")
    semantics <- switch(
        method,
        singler = "spearman_reference_score",
        scmap = "multi_similarity_consensus",
        symphony = "knn_vote_fraction"
    )
    list(
        adapter = method,
        adapter_implementation_version = ADAPTER_IMPLEMENTATION_VERSION,
        package_version = as.character(utils::packageVersion(package)),
        probability_semantics = semantics,
        conformal_eligible = FALSE,
        evidence_family = if (method %in% c("singler", "scmap")) "reference_similarity" else "latent_reference_mapping",
        seed = seed
    )
}

write_output <- function(frame, output, metadata) {
    frame <- frame[order(frame$fold_id, frame$partition, frame$observation_id), , drop = FALSE]
    if (anyDuplicated(frame[c("fold_id", "observation_id")])) stop_bridge("prediction_identity_not_unique")
    dir.create(dirname(output), recursive = TRUE, showWarnings = FALSE)
    if (grepl("\\.parquet$", output, ignore.case = TRUE)) {
        require_packages("arrow")
        arrow::write_parquet(frame, output)
    } else if (grepl("\\.(tsv|txt)$", output, ignore.case = TRUE)) {
        write.table(frame, output, sep = "\t", quote = FALSE, row.names = FALSE, na = "")
    } else stop_bridge("prediction_output_format_unsupported", output)
    metadata$output_sha256 <- sha256(output)
    metadata$n_predictions <- nrow(frame)
    metadata$partitions <- sort(unique(frame$partition))
    jsonlite::write_json(metadata, paste0(output, ".metadata.json"), auto_unbox = TRUE, pretty = TRUE)
}

main <- function() {
    args <- parse_args(commandArgs(trailingOnly = TRUE))
    output <- required_arg(args, "output")
    if (args$method == "scconform") {
        frame <- run_scconform(args)
        metadata <- attr(frame, "metadata")
        attr(frame, "metadata") <- NULL
        write_output(frame, output, metadata)
        return(invisible(NULL))
    }
    exchange_root <- required_arg(args, "exchange_root")
    asset_id <- required_arg(args, "asset_id")
    bundle <- read_bundle(exchange_root, asset_id)
    folds <- read_split(required_arg(args, "split_manifest"), asset_id, bundle$observations)
    seed <- as.integer(args$seed %||% "0")
    if (is.na(seed)) stop_bridge("seed_invalid")
    frame <- switch(
        args$method,
        singler = run_singler(bundle, folds),
        scmap = run_scmap(bundle, folds),
        symphony = run_symphony(bundle, folds, seed)
    )
    metadata <- method_metadata(args$method, seed)
    label_universe <- as.character(bundle$manifest$label_universe)
    if (!length(label_universe) || anyNA(label_universe) || any(!nzchar(label_universe))) {
        stop_bridge("bundle_label_universe_invalid")
    }
    metadata$fold_missing_training_labels <- lapply(folds, function(partition) {
        sort(setdiff(label_universe, unique(bundle$observations$true_label[partition == "train"])))
    })
    metadata$split_manifest_sha256 <- sha256(required_arg(args, "split_manifest"))
    split <- jsonlite::fromJSON(required_arg(args, "split_manifest"), simplifyVector = TRUE)
    metadata$split_manifest_id <- split$split_manifest_id
    metadata$benchmark_spec_ref <- split$benchmark_spec_ref
    metadata$input_bundle_sha256 <- setNames(
        list(sha256(file.path(exchange_root, asset_id, "bundle.json"))), asset_id
    )
    write_output(frame, output, metadata)
}

tryCatch(main(), error = function(error) {
    message(conditionMessage(error))
    quit(status = 2L, save = "no")
})
