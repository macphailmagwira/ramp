class AppError(Exception):
    status_code = 400
    code = "APP_ERROR"
    message = "An application error occurred."

    def __init__(self, message=None, **context):
        if message:
            self.message = message
        self.context = context
