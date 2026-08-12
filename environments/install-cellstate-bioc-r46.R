options(repos = c(CRAN = "https://cloud.r-project.org"))

install.packages(
  sprintf(
    "https://cloud.r-project.org/src/contrib/BiocManager_%s.tar.gz",
    Sys.getenv("BRIDGE_BIOCMANAGER_VERSION")
  ),
  repos = NULL,
  type = "source"
)
install.packages(
  sprintf(
    "https://cloud.r-project.org/src/contrib/remotes_%s.tar.gz",
    Sys.getenv("BRIDGE_REMOTES_VERSION")
  ),
  repos = NULL,
  type = "source"
)
digest_version <- Sys.getenv("BRIDGE_DIGEST_VERSION")
if (!requireNamespace("digest", quietly = TRUE) ||
    as.character(utils::packageVersion("digest")) != digest_version) {
  install.packages(
    sprintf("https://cloud.r-project.org/src/contrib/digest_%s.tar.gz", digest_version),
    repos = NULL,
    type = "source"
  )
}
if (as.character(BiocManager::version()) != Sys.getenv("BRIDGE_BIOC_VERSION")) {
  stop("Bioconductor release does not match BRIDGE_BIOC_VERSION")
}

cran_dependencies <- c(
  "Rcpp", "RcppArmadillo", "RcppProgress", "dplyr", "cowplot", "ggplot2",
  "tibble", "rlang", "RhpcBLASctl", "cli", "uwot", "irlba", "purrr",
  "magrittr", "data.table", "tidyr", "RColorBrewer", "RANN"
)
missing_cran <- cran_dependencies[
  !vapply(cran_dependencies, requireNamespace, logical(1), quietly = TRUE)
]
if (length(missing_cran)) {
  install.packages(missing_cran, Ncpus = 1L)
}

igraph_version <- Sys.getenv("BRIDGE_IGRAPH_VERSION")
if (!requireNamespace("igraph", quietly = TRUE) ||
    as.character(utils::packageVersion("igraph")) != igraph_version) {
  archive <- Sys.getenv("BRIDGE_IGRAPH_ARCHIVE")
  source <- if (nzchar(archive)) archive else sprintf(
    "https://cloud.r-project.org/src/contrib/igraph_%s.tar.gz", igraph_version
  )
  install.packages(source, repos = NULL, type = "source", Ncpus = 1L)
}

for (package in c(
  "Rhdf5lib", "rhdf5filters", "rhdf5", "SparseArray", "DelayedArray",
  "SummarizedExperiment", "SingleCellExperiment", "beachmat", "BiocNeighbors",
  "SingleR", "scmap", "UCell"
)) {
  if (!requireNamespace(package, quietly = TRUE)) {
    BiocManager::install(package, ask = FALSE, update = FALSE, Ncpus = 1L)
  }
}

if (!requireNamespace("scConform", quietly = TRUE)) {
  archive <- Sys.getenv("BRIDGE_SCCONFORM_ARCHIVE")
  if (nzchar(archive)) {
    install.packages(archive, repos = NULL, type = "source", Ncpus = 1L)
  } else {
    BiocManager::install("scConform", ask = FALSE, update = FALSE, Ncpus = 1L)
  }
}

install_snapshot <- function(repository, ref, archive_env) {
  archive <- Sys.getenv(archive_env)
  if (nzchar(archive)) {
    if (!file.exists(archive)) stop(sprintf("Snapshot archive not found: %s", archive))
    remotes::install_local(archive, dependencies = FALSE, upgrade = "never")
  } else {
    remotes::install_github(
      repository, ref = ref, dependencies = FALSE, upgrade = "never"
    )
  }
}

install_snapshot(
  "immunogenomics/harmony",
  ref = Sys.getenv("BRIDGE_HARMONY_COMMIT"),
  archive_env = "BRIDGE_HARMONY_ARCHIVE"
)
install_snapshot(
  "immunogenomics/symphony",
  ref = Sys.getenv("BRIDGE_SYMPHONY_COMMIT"),
  archive_env = "BRIDGE_SYMPHONY_ARCHIVE"
)

expected <- c(
  digest = Sys.getenv("BRIDGE_DIGEST_VERSION"),
  SingleR = Sys.getenv("BRIDGE_SINGLER_VERSION"),
  scmap = Sys.getenv("BRIDGE_SCMAP_VERSION"),
  scConform = Sys.getenv("BRIDGE_SCCONFORM_VERSION"),
  UCell = Sys.getenv("BRIDGE_UCELL_VERSION")
)
actual <- vapply(names(expected), function(package) as.character(packageVersion(package)), "")
if (!identical(actual, expected)) {
  stop(sprintf("Bioconductor version mismatch: %s", paste(names(actual), actual, collapse = ", ")))
}
