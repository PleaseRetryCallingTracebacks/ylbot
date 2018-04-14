# --- Basic exceptions class ---
class EduError(Exception):
    pass
# ------------------------------


# --- DataHandler Exceptions ---
class IncorrectSchoolError(EduError):
    pass
class IncorrectLessonError(EduError):
    pass
class HomeworkExistsError(EduError):
    # If database already contains any notes for homework
    # In this case you need to use DataHandler.hw_edit() instead DataHandler.hw_write()
    pass
class HomeworkNotFoundError(EduError):
    pass
# ------------------------------


# ----- EduAPI Exceptions ------
class AuthFailedError(EduError):
    args = 'Auth failed!'
    pass
class DriverError(EduError):
    args = 'Driver Error'
    pass
class TimeoutError(EduError):
    args = 'Timeout Error'
    pass
# ------------------------------