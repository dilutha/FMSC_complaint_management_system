from django.contrib.auth import authenticate, password_validation
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import Q
from rest_framework import serializers

from apps.cases.models import Authority

from .models import Role, User

def check_password_strength(password, user, field):
    """Run Django's password validators, reporting errors against `field`."""
    try:
        password_validation.validate_password(password, user)
    except DjangoValidationError as exc:
        raise serializers.ValidationError({field: list(exc.messages)}) from exc


#: Only resolving-department users belong to a department (and so act on its cases).
AUTHORITY_MEMBER_ROLES = {Role.AUTHORITY}


class AuthorityRefSerializer(serializers.ModelSerializer):
    class Meta:
        model = Authority
        fields = ["id", "name"]


class MeSerializer(serializers.ModelSerializer):
    """Signed-in user. Backwards compatible with the placeholder contract
    (id, username, display_name, email, role, is_case_admin)."""

    role_label = serializers.CharField(source="get_role_display", read_only=True)
    capabilities = serializers.SerializerMethodField()
    authorities = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ["id", "username", "display_name", "first_name", "last_name", "email", "role", "role_label",
                  "is_case_admin", "department", "contact_number", "capabilities", "authorities", "workspace"]
        read_only_fields = ["id", "username", "display_name", "first_name", "last_name", "email", "role",
                            "role_label", "is_case_admin", "capabilities", "authorities", "workspace"]

    def get_capabilities(self, user) -> list[str]:
        return user.capabilities()

    def get_authorities(self, user) -> list[dict]:
        return AuthorityRefSerializer(user.authorities.filter(is_active=True), many=True).data


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=254, help_text="Username or email address")
    password = serializers.CharField(max_length=128, write_only=True, trim_whitespace=False)

    def validate(self, attrs):
        identifier = attrs["username"].strip()
        username = identifier
        if "@" in identifier:
            matches = list(User.objects.filter(email__iexact=identifier).values_list("username", flat=True)[:2])
            if len(matches) == 1:
                username = matches[0]
        user = authenticate(self.context.get("request"), username=username, password=attrs["password"])
        if user is None:
            # Same message whether the account exists or not (no user enumeration).
            raise serializers.ValidationError("Incorrect username or password.", code="authorization")
        attrs["user"] = user
        return attrs


class ChangePasswordSerializer(serializers.Serializer):
    current_password = serializers.CharField(max_length=128, write_only=True, trim_whitespace=False)
    new_password = serializers.CharField(max_length=128, write_only=True, trim_whitespace=False)

    def validate_current_password(self, value):
        if not self.context["request"].user.check_password(value):
            raise serializers.ValidationError("Your current password is incorrect.")
        return value

    def validate(self, attrs):
        check_password_strength(attrs["new_password"], self.context["request"].user, "new_password")
        return attrs


class UserAdminSerializer(serializers.ModelSerializer):
    """User management for system administrators."""

    role_label = serializers.CharField(source="get_role_display", read_only=True)
    password = serializers.CharField(write_only=True, required=False, trim_whitespace=False, max_length=128)
    authority_ids = serializers.PrimaryKeyRelatedField(
        queryset=Authority.objects.all(), many=True, required=False, source="authorities"
    )

    class Meta:
        model = User
        fields = ["id", "username", "email", "first_name", "last_name", "role", "role_label", "department",
                  "contact_number", "is_active", "date_joined", "last_login", "authority_ids", "password"]
        read_only_fields = ["id", "date_joined", "last_login"]

    def validate_email(self, value):
        value = (value or "").strip()
        if value:
            clash = User.objects.filter(email__iexact=value)
            if self.instance:
                clash = clash.exclude(pk=self.instance.pk)
            if clash.exists():
                raise serializers.ValidationError("Another account already uses this email address.")
        return value

    def validate(self, attrs):
        request_user = self.context["request"].user
        if self.instance is None and not attrs.get("password"):
            raise serializers.ValidationError({"password": ["A password is required for a new account."]})
        if attrs.get("password"):
            candidate = User(**{k: v for k, v in attrs.items() if k in ("username", "email", "first_name", "last_name")})
            check_password_strength(attrs["password"], self.instance or candidate, "password")
        if self.instance is not None and self.instance.pk == request_user.pk:
            if "role" in attrs and attrs["role"] != self.instance.role:
                raise serializers.ValidationError({"role": ["You cannot change your own role."]})
            if attrs.get("is_active") is False:
                raise serializers.ValidationError({"is_active": ["You cannot deactivate your own account."]})
        role = attrs.get("role", self.instance.role if self.instance else Role.STUDENT)
        authorities = attrs.get("authorities")
        if authorities and role not in AUTHORITY_MEMBER_ROLES:
            raise serializers.ValidationError(
                {"authority_ids": ["Only resolving-department users can belong to a department."]}
            )
        if authorities and len(authorities) > 1:
            raise serializers.ValidationError(
                {"authority_ids": ["A department user belongs to exactly one department."]}
            )
        return attrs


class AuthorityAdminSerializer(serializers.ModelSerializer):
    member_count = serializers.SerializerMethodField()

    class Meta:
        model = Authority
        fields = ["id", "name", "code", "unit", "officer_name", "designation", "email", "phone", "is_active",
                  "member_count"]

    def get_member_count(self, obj) -> int:
        return obj.members.filter(is_active=True).count()


def search_users(qs, term):
    term = term.strip()[:100]
    return qs.filter(
        Q(username__icontains=term) | Q(email__icontains=term) | Q(first_name__icontains=term)
        | Q(last_name__icontains=term)
    )
