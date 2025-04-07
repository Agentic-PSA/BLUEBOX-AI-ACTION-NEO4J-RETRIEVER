

class GetProductForm:

    def __init__(self, raw_data: dict):
        self.raw_data: dict = raw_data
        self.cleaned_data: dict = {}
        self.errors: list = []

    def is_valid(self) -> bool:
        ean: str = self.raw_data.get('ean', None)
        pn: str = self.raw_data.get('pn', None)
        name: str = self.raw_data.get('name', None)
        action: str = self.raw_data.get('action', None)

        if not ean and not pn and not name and not action:
            self.errors.append({'data': 'Incorrect input. Please provide EAN, PN, Action code or name'})

        if self.errors:
            return False

        self.cleaned_data = self.raw_data

        return True
