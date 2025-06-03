class AddValuesForm:

    def __init__(self, raw_data: dict):
        self.raw_data: dict = raw_data
        self.cleaned_data: dict = {}
        self.errors: list = []

    def is_valid(self) -> bool:
        label: str = self.raw_data.get('label', '')
        parameters_dict: dict = self.raw_data.get('parameters_dict', {})

        if not label:
            self.errors.append({'label': 'Label is missing'})
        if not parameters_dict:
            self.errors.append({'parameters_dict': 'parameters_dict are missing'})


        if self.errors:
            return False

        self.cleaned_data = self.raw_data

        return True
