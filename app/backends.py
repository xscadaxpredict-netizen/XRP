from django.contrib.auth.backends import ModelBackend
from django.contrib.auth import get_user_model
from django.db.models import Q

class EmailOrUsernameModelBackend(ModelBackend):
    """
    Custom authentication backend that allows users to log in
    using either their username or their email address.
    """
    def authenticate(self, request, username=None, password=None, **kwargs):
        UserModel = get_user_model()
        if username is None:
            username = kwargs.get(UserModel.USERNAME_FIELD)
        if not username or not password:
            return None

        # Search for users matching username or email (case-insensitive)
        users = UserModel.objects.filter(
            Q(username__iexact=username) | Q(email__iexact=username)
        )
        for user in users:
            if user.check_password(password) and self.user_can_authenticate(user):
                return user
        return None
