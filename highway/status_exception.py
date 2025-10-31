from highway.workflow_model import Status


class StatusException(Exception):
    def __init__(self, status: Status, *args) -> None:
        if status.message:
            args = args + (status.message,)
        super().__init__(*args)
        self.status = status
