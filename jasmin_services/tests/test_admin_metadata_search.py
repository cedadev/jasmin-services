"""Tests for admin metadata search functionality."""

import django.contrib.auth
import django.test
from django.contrib.contenttypes.models import ContentType

import jasmin_metadata.models
import jasmin_services.models
from jasmin_services.admin.grant import GrantAdmin
from jasmin_services.admin.request import RequestAdmin


class AdminMetadataSearchTestCase(django.test.TestCase):
    """Test metadata search functionality in admin classes."""

    def setUp(self):
        """Set up test data with metadata."""
        # Create user
        User = django.contrib.auth.get_user_model()
        self.user1 = User.objects.create_user(
            username="testuser1", email="testuser1@example.com", first_name="Test", last_name="User"
        )
        self.user2 = User.objects.create_user(
            username="testuser2",
            email="testuser2@example.com",
            first_name="Another",
            last_name="Person",
        )

        # Create category and service
        self.category = jasmin_services.models.Category.objects.create(
            name="test_cat", long_name="Test Category", position=1
        )
        self.service = jasmin_services.models.Service.objects.create(
            category=self.category,
            name="test_service",
            summary="Test Service",
            description="A service for testing",
        )

        # Create role
        self.role = jasmin_services.models.Role.objects.create(
            service=self.service, name="test_role", description="Test role"
        )

        # Create access objects
        self.access1 = jasmin_services.models.Access.objects.create(role=self.role, user=self.user1)
        self.access2 = jasmin_services.models.Access.objects.create(role=self.role, user=self.user2)

        # Create grants
        self.grant1 = jasmin_services.models.Grant.objects.create(
            access=self.access1, granted_by="admin"
        )
        self.grant2 = jasmin_services.models.Grant.objects.create(
            access=self.access2, granted_by="admin"
        )

        # Create requests
        self.request1 = jasmin_services.models.Request.objects.create(
            access=self.access1, requested_by="testuser1"
        )
        self.request2 = jasmin_services.models.Request.objects.create(
            access=self.access2, requested_by="testuser2"
        )

        # Create metadata for grants
        grant_ct = ContentType.objects.get_for_model(jasmin_services.models.Grant)
        jasmin_metadata.models.Metadatum.objects.create(
            content_type=grant_ct,
            object_id=self.grant1.pk,
            key="project_name",
            value="Climate Research Project",
        )
        jasmin_metadata.models.Metadatum.objects.create(
            content_type=grant_ct,
            object_id=self.grant1.pk,
            key="institution",
            value="University of Oxford",
        )
        jasmin_metadata.models.Metadatum.objects.create(
            content_type=grant_ct,
            object_id=self.grant2.pk,
            key="project_name",
            value="Ocean Data Analysis",
        )
        jasmin_metadata.models.Metadatum.objects.create(
            content_type=grant_ct,
            object_id=self.grant2.pk,
            key="storage_quota",
            value=500,
        )

        # Create metadata for requests
        request_ct = ContentType.objects.get_for_model(jasmin_services.models.Request)
        jasmin_metadata.models.Metadatum.objects.create(
            content_type=request_ct,
            object_id=self.request1.pk,
            key="project_description",
            value="Analyzing climate data for polar regions",
        )
        jasmin_metadata.models.Metadatum.objects.create(
            content_type=request_ct,
            object_id=self.request1.pk,
            key="contact_email",
            value="researcher@oxford.ac.uk",
        )
        jasmin_metadata.models.Metadatum.objects.create(
            content_type=request_ct,
            object_id=self.request2.pk,
            key="project_description",
            value="Marine biology research project",
        )
        jasmin_metadata.models.Metadatum.objects.create(
            content_type=request_ct, object_id=self.request2.pk, key="urgency_level", value="High"
        )

        # Initialize admin instances
        self.grant_admin = GrantAdmin(jasmin_services.models.Grant, None)
        self.request_admin = RequestAdmin(jasmin_services.models.Request, None)

    def test_grant_admin_metadata_search_text(self):
        """Test searching grants by text metadata values."""
        queryset = jasmin_services.models.Grant.objects.all()

        # Search for "Climate" should find grant1
        results, use_distinct = self.grant_admin.get_search_results(None, queryset, "Climate")
        self.assertTrue(use_distinct)
        self.assertIn(self.grant1, results)
        self.assertNotIn(self.grant2, results)

        # Search for "Oxford" should find grant1
        results, use_distinct = self.grant_admin.get_search_results(None, queryset, "Oxford")
        self.assertTrue(use_distinct)
        self.assertIn(self.grant1, results)
        self.assertNotIn(self.grant2, results)

        # Search for "Ocean" should find grant2
        results, use_distinct = self.grant_admin.get_search_results(None, queryset, "Ocean")
        self.assertTrue(use_distinct)
        self.assertNotIn(self.grant1, results)
        self.assertIn(self.grant2, results)

    def test_grant_admin_metadata_search_numeric(self):
        """Test searching grants by numeric metadata values."""
        queryset = jasmin_services.models.Grant.objects.all()

        # Search for "500" should find grant2
        results, use_distinct = self.grant_admin.get_search_results(None, queryset, "500")
        self.assertTrue(use_distinct)
        self.assertNotIn(self.grant1, results)
        self.assertIn(self.grant2, results)

    def test_grant_admin_metadata_search_case_insensitive(self):
        """Test that metadata search is case insensitive."""
        queryset = jasmin_services.models.Grant.objects.all()

        # Search for "climate" (lowercase) should find grant1
        results, use_distinct = self.grant_admin.get_search_results(None, queryset, "climate")
        self.assertTrue(use_distinct)
        self.assertIn(self.grant1, results)

        # Search for "OXFORD" (uppercase) should find grant1
        results, use_distinct = self.grant_admin.get_search_results(None, queryset, "OXFORD")
        self.assertTrue(use_distinct)
        self.assertIn(self.grant1, results)

    def test_request_admin_metadata_search_text(self):
        """Test searching requests by text metadata values."""
        queryset = jasmin_services.models.Request.objects.all()

        # Search for "polar" should find request1
        results, use_distinct = self.request_admin.get_search_results(None, queryset, "polar")
        self.assertTrue(use_distinct)
        self.assertIn(self.request1, results)
        self.assertNotIn(self.request2, results)

        # Search for "marine" should find request2
        results, use_distinct = self.request_admin.get_search_results(None, queryset, "marine")
        self.assertTrue(use_distinct)
        self.assertNotIn(self.request1, results)
        self.assertIn(self.request2, results)

        # Search for "oxford.ac.uk" should find request1
        results, use_distinct = self.request_admin.get_search_results(
            None, queryset, "oxford.ac.uk"
        )
        self.assertTrue(use_distinct)
        self.assertIn(self.request1, results)
        self.assertNotIn(self.request2, results)

    def test_request_admin_metadata_search_case_insensitive(self):
        """Test that request metadata search is case insensitive."""
        queryset = jasmin_services.models.Request.objects.all()

        # Search for "HIGH" (uppercase) should find request2
        results, use_distinct = self.request_admin.get_search_results(None, queryset, "HIGH")
        self.assertTrue(use_distinct)
        self.assertNotIn(self.request1, results)
        self.assertIn(self.request2, results)

    def test_metadata_search_no_results(self):
        """Test searching for terms that don't exist in metadata."""
        queryset = jasmin_services.models.Grant.objects.all()

        # Search for non-existent term
        results, use_distinct = self.grant_admin.get_search_results(
            None, queryset, "nonexistentterm"
        )
        self.assertFalse(use_distinct)  # No metadata matches, no combining needed
        self.assertEqual(list(results), [])

    def test_empty_search_term(self):
        """Test that empty search terms don't crash."""
        queryset = jasmin_services.models.Grant.objects.all()

        # Empty search term should return original queryset
        results, use_distinct = self.grant_admin.get_search_results(None, queryset, "")
        self.assertFalse(use_distinct)
        self.assertEqual(list(results), list(queryset))

        # None search term should return original queryset
        results, use_distinct = self.grant_admin.get_search_results(None, queryset, None)
        self.assertFalse(use_distinct)
        self.assertEqual(list(results), list(queryset))

    def test_metadata_search_with_standard_search(self):
        """Test that metadata search combines with standard search fields."""
        queryset = jasmin_services.models.Grant.objects.all()

        # Search for username should work (standard search)
        results, use_distinct = self.grant_admin.get_search_results(None, queryset, "testuser1")
        # Should find grant1 through standard user search
        self.assertIn(self.grant1, results)

    def test_special_characters_in_metadata(self):
        """Test searching metadata with special characters."""
        # Add metadata with special characters
        grant_ct = ContentType.objects.get_for_model(jasmin_services.models.Grant)
        jasmin_metadata.models.Metadatum.objects.create(
            content_type=grant_ct,
            object_id=self.grant1.pk,
            key="special_field",
            value="test@domain.com & other/special-chars_123",
        )

        queryset = jasmin_services.models.Grant.objects.all()

        # Search for part with special characters
        results, use_distinct = self.grant_admin.get_search_results(
            None, queryset, "test@domain.com"
        )
        self.assertTrue(use_distinct)
        self.assertIn(self.grant1, results)

        # Search for part with underscore
        results, use_distinct = self.grant_admin.get_search_results(
            None, queryset, "special-chars_123"
        )
        self.assertTrue(use_distinct)
        self.assertIn(self.grant1, results)

    def test_none_metadata_values(self):
        """Test that None metadata values don't cause crashes."""
        # Create metadata with None value
        grant_ct = ContentType.objects.get_for_model(jasmin_services.models.Grant)
        jasmin_metadata.models.Metadatum.objects.create(
            content_type=grant_ct, object_id=self.grant1.pk, key="null_field", value=None
        )

        queryset = jasmin_services.models.Grant.objects.all()

        # Search should not crash with None values
        results, use_distinct = self.grant_admin.get_search_results(None, queryset, "anything")
        # Should complete without error
        self.assertIsNotNone(results)

    def test_partial_matches(self):
        """Test that partial string matches work correctly."""
        queryset = jasmin_services.models.Grant.objects.all()

        # Search for partial match "Clim" should find "Climate Research Project"
        results, use_distinct = self.grant_admin.get_search_results(None, queryset, "Clim")
        self.assertTrue(use_distinct)
        self.assertIn(self.grant1, results)

        # Search for partial match "Data" should find "Ocean Data Analysis"
        results, use_distinct = self.grant_admin.get_search_results(None, queryset, "Data")
        self.assertTrue(use_distinct)
        self.assertIn(self.grant2, results)
