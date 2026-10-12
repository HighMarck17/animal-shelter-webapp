from django.contrib import admin # pyright: ignore[reportMissingModuleSource]
from django.urls import path, include # pyright: ignore[reportMissingModuleSource]
from django.conf import settings # pyright: ignore[reportMissingModuleSource]
from django.conf.urls.static import static # pyright: ignore[reportMissingModuleSource]
from rest_framework.routers import DefaultRouter # pyright: ignore[reportMissingImports]
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView, SpectacularRedocView # pyright: ignore[reportMissingImports]

# Import ViewSets
from apps.dogs.api_views import DogViewSet, BreedViewSet
from apps.contacts.api_views import ContactMessageViewSet
from apps.faq.api_views import FAQViewSet, FAQCategoryViewSet

# Customize the admin title
admin.site.site_header = f"{settings.SHELTER_NAME} - Amministrazione"
admin.site.site_title = f"{settings.SHELTER_NAME} Admin"
admin.site.index_title = "Benvenuto nell'area di amministrazione"

# Router API
router = DefaultRouter()
router.register(r'dogs', DogViewSet, basename='dog')
router.register(r'breeds', BreedViewSet, basename='breed')
router.register(r'contacts', ContactMessageViewSet, basename='contact')
router.register(r'faqs', FAQViewSet, basename='faq')
router.register(r'faq-categories', FAQCategoryViewSet, basename='faq-category')

# Custom paths
ADMIN_PATH = getattr(settings, 'ADMIN_URL', 'admin/')
API_PATH = getattr(settings, 'API_URL', 'api/v1/')
API_SCHEMA_PATH = getattr(settings, 'API_SCHEMA_URL', 'api/schema/')
API_DOCS_PATH = getattr(settings, 'API_DOCS_URL', 'api/docs/')
API_REDOC_PATH = getattr(settings, 'API_REDOC_URL', 'api/redoc/')


urlpatterns = [
    # Admin with a custom URL
    path(ADMIN_PATH, admin.site.urls),

    # API with custom URLs
    path(API_PATH, include(router.urls)),
    path(API_SCHEMA_PATH, SpectacularAPIView.as_view(), name='schema'),
    path(API_DOCS_PATH, SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path(API_REDOC_PATH, SpectacularRedocView.as_view(url_name='schema'), name='redoc'),
    
    # Frontend pages
    path('', include('apps.homepage.urls')),
    path('dogs/', include('apps.dogs.urls')),
    path('contacts/', include('apps.contacts.urls')),
    path('faq/', include('apps.faq.urls')),
]

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

    # Debug toolbar — only when installed (development.py), so DEBUG=True with
    # the test or production requirements does not crash on import
    if 'debug_toolbar' in settings.INSTALLED_APPS:
        import debug_toolbar # pyright: ignore[reportMissingImports]
        urlpatterns += [
            path('__debug__/', include(debug_toolbar.urls)),
        ]
