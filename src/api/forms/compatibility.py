

class CompatibilityForm:

    def __init__(self, raw_data: dict):
        self.raw_data: dict = raw_data
        self.cleaned_data: dict = {}
        self.errors: list = []

    def is_valid(self) -> bool:
        type1: str = self.raw_data.get('type1', '')
        type2: str = self.raw_data.get('type2','')
        type_compatibility:str = self.raw_data.get('type_compatibility','')

        if not type1:
            self.errors.append({'type1': 'type1 is missing'})
        if not type2:
            self.errors.append({'type2': 'type2 is missing'})
        if not type_compatibility:
            self.errors.append({'type_compatibility': 'type_compatibility is missing'})
        elif not isinstance(type_compatibility, str):
            self.errors.append({'type_compatibility': 'type_compatibility is incorrect'})

        # if type_compatibility == "compatible":
        #     type1_parameters: list  = self.raw_data.get('type1_parameters', [])
        #     type2_parameters: list  = self.raw_data.get('type2_parameters', [])
        #     if not type1_parameters:
        #         self.errors.append({'type1_parameters': 'type1_parameters is missing'})
        #     if not type2_parameters:
        #         self.errors.append({'type2_parameters': 'type2_parameters is missing'})


        if self.errors:
            return False

        self.cleaned_data = self.raw_data

        return True
