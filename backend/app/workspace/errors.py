class WorkspaceError(RuntimeError):
    code = "WORKSPACE_ERROR"


class WorkspaceNotFoundError(WorkspaceError):
    code = "WORKSPACE_NOT_FOUND"


class WorkspaceFileNotFoundError(WorkspaceError):
    code = "WORKSPACE_FILE_NOT_FOUND"


class UnsafeWorkspacePathError(WorkspaceError):
    code = "UNSAFE_WORKSPACE_PATH"


class WorkspaceSymlinkError(UnsafeWorkspacePathError):
    code = "WORKSPACE_SYMLINK_REJECTED"


class WorkspaceFileTooLargeError(WorkspaceError):
    code = "WORKSPACE_FILE_TOO_LARGE"


class WorkspaceQuotaExceededError(WorkspaceError):
    code = "WORKSPACE_QUOTA_EXCEEDED"


class WorkspaceFileTypeError(WorkspaceError):
    code = "WORKSPACE_FILE_TYPE_REJECTED"


class WorkspaceEncodingError(WorkspaceError):
    code = "WORKSPACE_ENCODING_ERROR"
