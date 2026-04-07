from django import forms

from .parsers import get_supported_extensions
from .parsers.base import ParseError
from .services import parse_keywords_from_file


class KeywordUploadForm(forms.Form):
    """Form for uploading a CSV file of keywords.

    Parsing happens inside clean_file so any format errors surface as
    Django form validation errors before the view logic runs.
    """

    file = forms.FileField(
        widget=forms.FileInput(
            attrs={
                'class': 'block w-full text-sm text-gray-500 file:mr-4 file:py-2 file:px-4 file:rounded-lg file:border-0 file:text-sm file:font-medium file:bg-blue-50 file:text-blue-700 hover:file:bg-blue-100',
                'accept': ','.join(get_supported_extensions()),
            }
        ),
    )

    def clean_file(self):
        """Parse the uploaded file and attach the keyword list to cleaned_data.

        Raises ValidationError if the file type is not supported, encoding is wrong,
        the CSV structure is malformed, the file is empty, too large, or exceeds
        the 100 keyword limit.
        """
        uploaded_file = self.cleaned_data['file']

        import os

        ext = os.path.splitext(uploaded_file.name)[1].lower()
        allowed = get_supported_extensions()
        if ext not in allowed:
            raise forms.ValidationError(f'Unsupported file type "{ext or "(none)"}". Please upload a CSV file.')

        try:
            keywords = parse_keywords_from_file(uploaded_file)
        except ParseError as e:
            raise forms.ValidationError(str(e))
        self.cleaned_data['parsed_keywords'] = keywords
        return uploaded_file
