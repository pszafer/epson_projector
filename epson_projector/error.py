"""Error module."""


class ProjectorError(Exception):
    """Base class for errors."""

    def __init__(self, *args, message=None, **_kwargs):
        """Initialize base error."""

        super().__init__(*args, message)


class ProjectorUnavailableError(ProjectorError):
    """Projector unavailable error."""
