class MaterialValidationError(ValueError):
    pass


class LkpdValidationError(ValueError):
    pass


class MaterialTooLargeError(MaterialValidationError):
    pass

