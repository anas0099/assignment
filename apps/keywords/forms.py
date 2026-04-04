from django import forms

from .parsers import get_supported_extensions
from .parsers.base import ParseError
from .services import parse_keywords_from_file


class KeywordUploadForm(forms.Form):
    file = forms.FileField(
        widget=forms.FileInput(attrs={
            'class': 'block w-full text-sm text-gray-500 file:mr-4 file:py-2 file:px-4 file:rounded-lg file:border-0 file:text-sm file:font-medium file:bg-blue-50 file:text-blue-700 hover:file:bg-blue-100',
            'accept': ','.join(get_supported_extensions()),
        }),
    )

    def clean_file(self):
        uploaded_file = self.cleaned_data['file']
        try:
            keywords = parse_keywords_from_file(uploaded_file)
        except ParseError as e:
            raise forms.ValidationError(str(e))
        self.cleaned_data['parsed_keywords'] = keywords
        return uploaded_file
