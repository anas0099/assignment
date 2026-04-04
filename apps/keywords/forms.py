import csv
import io

from django import forms


class KeywordUploadForm(forms.Form):
    file = forms.FileField(
        widget=forms.FileInput(attrs={
            'class': 'block w-full text-sm text-gray-500 file:mr-4 file:py-2 file:px-4 file:rounded-lg file:border-0 file:text-sm file:font-medium file:bg-blue-50 file:text-blue-700 hover:file:bg-blue-100',
            'accept': '.csv',
        }),
    )

    def clean_file(self):
        uploaded_file = self.cleaned_data['file']
        if not uploaded_file.name.endswith('.csv'):
            raise forms.ValidationError('Only CSV files are allowed.')
        try:
            content = uploaded_file.read().decode('utf-8')
            uploaded_file.seek(0)
            reader = csv.reader(io.StringIO(content))
            keywords = []
            for row in reader:
                for cell in row:
                    stripped = cell.strip()
                    if stripped:
                        keywords.append(stripped)
            if not keywords:
                raise forms.ValidationError('CSV file is empty.')
            if len(keywords) > 100:
                raise forms.ValidationError('Maximum 100 keywords allowed per file.')
        except UnicodeDecodeError:
            raise forms.ValidationError('File must be UTF-8 encoded.')
        self.cleaned_data['parsed_keywords'] = keywords
        return uploaded_file
