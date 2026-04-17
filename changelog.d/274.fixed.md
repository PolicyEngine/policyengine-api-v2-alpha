`download_dataset` now rejects path-traversal filepaths (`../../etc/passwd`, absolute paths) that would write outside the Modal dataset cache root.
