

class AddTypeForm:

    def __init__(self, raw_data: dict):
        self.raw_data: dict = raw_data
        self.cleaned_data: dict = {}
        self.errors: list = []

    def is_valid(self) -> bool:
        code: str = self.raw_data.get('code', '')
        specification: str = self.raw_data.get('specification','')

        if not code:
            self.errors.append({'code': 'Code is missing'})
        if not specification:
            self.errors.append({'specification': 'Specification is missing'})


        if self.errors:
            return False

        self.cleaned_data = self.raw_data

        return True
