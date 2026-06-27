from rest_framework import serializers
from django.contrib.auth.models import User
from apage.models import Site
from website.models import Notification

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'first_name', 'last_name', 'email']

class SiteSerializer(serializers.ModelSerializer):
    zone_name = serializers.CharField(source='zone.name', read_only=True)

    class Meta:
        model = Site
        fields = ['id', 'name', 'zone_name']

class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = ['id', 'title', 'message', 'created_at', 'status']
