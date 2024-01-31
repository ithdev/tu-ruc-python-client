
class LengthError (Exception):
    def __init__(self, message):
        self.message = message
        super().__init__(self.message)

class InvalidRucError (Exception):
    def __init__(self, message):
        self.message = message
        super().__init__(self.message)

class SearchParameterError (Exception):
    def __init__(self, message):
        self.message = message
        super().__init__(self.message)
