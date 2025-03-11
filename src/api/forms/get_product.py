

class GetProductForm:

    def __init__(self, raw_data: dict):
        self.raw_data: dict = raw_data
        self.cleaned_data: dict = {}
        self.errors: list = []

    def is_valid(self) -> bool:
        ean: str = self.raw_data.get('ean', '')

        if not ean:
            self.errors.append({'ean': 'ean is missing'})

        if self.errors:
            return False

        self.cleaned_data = self.raw_data

        return True
