class FormatError(ValueError):
    """Unsupported or inconsistent serialized structure."""

class SyncError(ValueError):
    def __init__(self, code, detail=""):
        self.code = code
        self.detail = str(detail)
        super().__init__(code + (": " + self.detail if detail else ""))
