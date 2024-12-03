from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed
from .models import Company  # Import the model where you store API keys

class APIKeyAuthentication(BaseAuthentication):
    def authenticate(self, request):
        api_key = request.headers.get('Authorization')
        if not api_key:
            return None  # No API key provided

        try:
            # Remove 'Bearer ' if present
            api_key = api_key.replace('Bearer ', '')
            # Check if the API key is valid
            api_key_record = Company.objects.get(key=api_key)
        except Company.DoesNotExist:
            raise AuthenticationFailed('Invalid API key.')

        return (api_key_record, None)  # Authentication successful

    def authenticate_header(self, request):
        return 'Bearer'
