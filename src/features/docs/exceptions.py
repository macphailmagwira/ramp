class VersionConflict(Exception):
    """Raised when a PUT content's base_version does not match the stored version.

    Returned to the client as 409 with body {"version": ..., "blocks": ...}.
    """

    def __init__(self, version: int, blocks, label: str):
        self.version = version
        self.blocks = blocks
        self.label = label
        super().__init__("version conflict")
