from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.authtoken.views import ObtainAuthToken
from rest_framework.authtoken.models import Token
from datetime import timedelta
from django.utils import timezone
from apage.models import ServiceReport, Site
from website.models import Notification, FCMToken
from .serializers import UserSerializer, SiteSerializer, NotificationSerializer

class CustomAuthToken(ObtainAuthToken):
    def post(self, request, *args, **kwargs):
        print(f"Login attempt for data: {request.data}")
        try:
            serializer = self.serializer_class(data=request.data,
                                               context={'request': request})
            serializer.is_valid(raise_exception=True)
            user = serializer.validated_data['user']
            token, created = Token.objects.get_or_create(user=user)
            return Response({
                'token': token.key,
                'user': UserSerializer(user).data
            })
        except Exception as e:
            import traceback
            error_details = traceback.format_exc()
            print(f"LOGIN ERROR: {error_details}")
            return Response({'error': str(e), 'traceback': error_details}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class SiteVisitAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        today = timezone.now().date()
        all_sites = Site.objects.all()
        print(f"DEBUG: Found {all_sites.count()} sites for user {request.user}")
        visit_data = []

        for site in all_sites:
            last_visit = (
                ServiceReport.objects.filter(site=site)
                .order_by('-date_of_visit')
                .first()
            )

            due_date = None
            is_due = False
            location = "N/A"
            customer = "N/A"
            last_visit_date = None

            if last_visit:
                due_date = last_visit.date_of_visit + timedelta(days=15)
                is_due = due_date < today
                location = last_visit.location
                customer = last_visit.customer_name
                last_visit_date = last_visit.date_of_visit

            visit_data.append({
                'id': site.id,
                'site': SiteSerializer(site).data,
                'location': location,
                'customer_name': customer,
                'last_visit': str(last_visit_date) if last_visit_date else "No Visit",
                'next_visit': str(due_date) if due_date else "N/A",
                'is_due': is_due,
                'has_visit': bool(last_visit)
            })

        return Response(visit_data, status=status.HTTP_200_OK)

class NotificationAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if request.user.is_staff or request.user.is_superuser:
            notifications = Notification.objects.all().order_by('-created_at')[:20] # Last 20
        else:
            notifications = Notification.objects.filter(user=request.user).order_by('-created_at')[:20]
        
        serializer = NotificationSerializer(notifications, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

class SaveFCMTokenAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        fcm_token = request.data.get("fcm_token")
        print(f"🔥 ATTEMPTING TO REGISTER FCM TOKEN: {fcm_token[:15]}... FOR USER: {request.user.username}")
        
        if not fcm_token:
            return Response({"error": "fcm_token is required"}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            # Token is unique, so use it as lookup. If it exists, update the user.
            obj, created = FCMToken.objects.update_or_create(
                token=fcm_token,
                defaults={'user': request.user}
            )
            print(f"✅ FCM TOKEN SAVED. Created: {created}, Token: {obj.token[:15]}...")
            return Response({"status": "ok", "created": created}, status=status.HTTP_200_OK)
        except Exception as e:
            print(f"❌ DATABASE ERROR SAVING FCM TOKEN: {e}")
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
