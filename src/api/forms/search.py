

class SearchForm:

    def __init__(self, raw_data: dict):
        self.raw_data: dict = raw_data
        self.cleaned_data: dict = {}
        self.errors: list = []

    def is_valid(self) -> bool:
        query: str = self.raw_data.get('query', '')

        if not query:
            self.errors.append({'query': 'query is missing'})

        if self.errors:
            return False

        self.cleaned_data = self.raw_data

        return True
