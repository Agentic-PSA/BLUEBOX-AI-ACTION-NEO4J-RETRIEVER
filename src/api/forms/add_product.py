

class AddProductForm:

    def __init__(self, raw_data: dict):
        self.raw_data: dict = raw_data
        self.cleaned_data: dict = {}
        self.errors: list = []

    def is_valid(self) -> bool:
        node_type: str = self.raw_data.get('type', '')
        properties: dict = self.raw_data.get('properties', {})
        additional_types: list = self.raw_data.get('additional_types', [])
        if not node_type:
            self.errors.append({'type': 'Type is missing'})
        if not properties:
            self.errors.append({'properties': 'Properties are missing'})


        if self.errors:
            return False

        self.cleaned_data = self.raw_data

        return True
