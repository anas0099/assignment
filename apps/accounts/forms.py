from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm

User = get_user_model()


class SignUpForm(UserCreationForm):
    """Registration form that adds an email field to Django's built-in UserCreationForm.

    TailwindCSS classes are applied to all inputs via __init__ so the template
    does not need to handle styling manually.
    """
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={
            'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
            'placeholder': 'you@example.com',
        }),
    )

    class Meta:
        model = User
        fields = ('username', 'email', 'password1', 'password2')

    def __init__(self, *args, **kwargs):
        """Apply consistent Tailwind input styling to all form fields."""
        super().__init__(*args, **kwargs)
        input_class = 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent'
        self.fields['username'].widget.attrs.update({
            'class': input_class,
            'placeholder': 'Username',
        })
        self.fields['password1'].widget.attrs.update({
            'class': input_class,
            'placeholder': 'Password',
        })
        self.fields['password2'].widget.attrs.update({
            'class': input_class,
            'placeholder': 'Confirm password',
        })

    def save(self, commit=True):
        """Save the user and persist the email field which UserCreationForm ignores by default."""
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        if commit:
            user.save()
        return user


class LoginForm(forms.Form):
    """Simple login form with username and password fields."""
    username = forms.CharField(
        widget=forms.TextInput(attrs={
            'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
            'placeholder': 'Username',
        }),
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
            'placeholder': 'Password',
        }),
    )
