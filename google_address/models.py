from django.db import models
from django.core.exceptions import ObjectDoesNotExist
from django.db.models import Count

ADDRESS_PRESENTATION_TYPES = ('long_name', 'short_name',)


class AddressComponentType(models.Model):
    name = models.CharField(max_length=100)

    def __str__(self):
        return self.name


class AddressComponent(models.Model):
    long_name = models.CharField(max_length=400)
    short_name = models.CharField(max_length=400)
    types = models.ManyToManyField(AddressComponentType)

    def __str__(self):
        return self.long_name

    @staticmethod
    def get_or_create_component(api_component):
        # Look for component with same name and type
        component = AddressComponent.objects.annotate(count=Count('types')).filter(long_name=api_component['long_name'],
                                                                                   short_name=api_component[
                                                                                       'short_name'])
        for component_type in api_component['types']:
            component = component.filter(types__name=component_type)
        component = component.filter(count=len(api_component['types']))

        if not component.count():
            # Component not found, creating
            component = AddressComponent(long_name=api_component['long_name'], short_name=api_component['short_name'])
            component.save()
        else:
            # We clear and recreate types because
            # sometimes google changes types for a given component
            component = component.first()
            component.types.clear()
            component.save()

        # Add types for component
        for api_component_type in api_component['types']:
            try:
                component_type = AddressComponentType.objects.get(name=api_component_type)
            except ObjectDoesNotExist:
                component_type = AddressComponentType(name=api_component_type)
                component_type.save()
            component.types.add(component_type)

        return component


class AddressSets(models.QuerySet):
    """ If you save city name from input to raw ->
        you can use `unique_cities` queryset in model.Manager
        like `Address.objects.unique_cities()`
    """
    def validated(self):
        return self.filter(validated=True)

    def unique_cities(self):
        return self.distinct('city_state').values('city_state', 'id')


class AddressManager(models.Manager):
    def get_queryset(self):
        return AddressSets(self.model, using=self._db)

    def unique_cities(self):
        return self.get_queryset().unique_cities().order_by('city_state')


class Address(models.Model):
    raw = models.CharField(max_length=400, blank=True, null=True)
    raw2 = models.CharField(max_length=400, blank=True, null=True)
    address_line = models.CharField(max_length=400, blank=True, null=True)
    city_state = models.CharField(max_length=400, blank=True, null=True)
    lat = models.FloatField('lat', blank=True, null=True)
    lng = models.FloatField('lng', blank=True, null=True)
    address_components = models.ManyToManyField(AddressComponent)
    objects = AddressManager()

    def get_city_state(self):
        state = self.address_components.filter(types__name='administrative_area_level_1')
        county = self.address_components.filter(types__name='administrative_area_level_2')
        locality = self.address_components.filter(types__name='locality')

        s = u""
        if locality.count():
            s += u"{}, ".format(locality[0].long_name)
        elif county.count():
            s += u"{}, ".format(county[0].long_name)

        if state.count():
            s += state[0].short_name

        return s

    @property
    def city(self):
        city = self.address_components.filter(types__name='locality').first()
        return str(city or '')

    @property
    def composite(self):
        return self.composed_address()

    def get_address(self):
        # Components types for address
        address = {'route': '', 'sublocality_level_1': '', 'administrative_area_level_2': '',
                   'administrative_area_level_1': '', 'country': '', 'street_number': ''}

        # Fill address dict
        for component in self.address_components.all():
            for component_type in component.types.all():
                if component_type.name in address:
                    address[component_type.name] = {'short_name': component.short_name,
                                                    'long_name': component.long_name}

        # Build address string
        string_address = ''
        if 'route' in address and isinstance(address['route'], dict):
            string_address += '{}, '.format(address['route']['long_name'])
        if 'route' in address and isinstance(address['street_number'], dict):
            string_address += '{}, '.format(address['street_number']['long_name'])
        if 'sublocality_level_1' in address and isinstance(address['sublocality_level_1'], dict):
            string_address += '{}, '.format(address['sublocality_level_1']['long_name'])
        if 'administrative_area_level_2' in address and isinstance(address['administrative_area_level_2'], dict):
            string_address += '{}, '.format(address['administrative_area_level_2']['long_name'])
        if 'administrative_area_level_1' in address and isinstance(address['administrative_area_level_1'], dict):
            string_address += '{}, '.format(address['administrative_area_level_1']['short_name'])
        if 'country' in address and isinstance(address['country'], dict):
            string_address += '{}, '.format(address['country']['long_name'])

        string_address = string_address.strip().strip(',')

        return string_address

    def composed_address(self, length=ADDRESS_PRESENTATION_TYPES[0], localized=True):
        """
        :param length: customize with 'long_name' or 'short_name'
        :param localized: :type boolean:
        :return: :type dict: address composed for BLP requirements and customization features
        """
        # Components types for address
        address = {'route': '', 'locality': '', 'administrative_area_level_2': '',
                   'administrative_area_level_1': '', 'country': '', 'street_number': ''}

        # Fill address dict
        for component in self.address_components.all():
            for component_type in component.types.all():
                if component_type.name in address:
                    address[component_type.name] = {'short_name': component.short_name,
                                                    'long_name': component.long_name}

        # Build address to dict or json
        composed = {'street': '', 'building_number': '', 'city_name': '', 'region_name': '', 'district_name': ''}
        if 'route' in address and isinstance(address['route'], dict):
            composed['street'] = address['route'][length]
        if 'route' in address and isinstance(address['street_number'], dict):
            composed['building_number'] = address['street_number'][length]
        if 'locality' in address and isinstance(address['locality'], dict):
            composed['city_name'] = address['locality'][length]
        if 'administrative_area_level_2' in address and isinstance(address['administrative_area_level_2'], dict):
            composed['region_name'] = address['administrative_area_level_2'][length]
        if 'administrative_area_level_1' in address and isinstance(address['administrative_area_level_1'], dict):
            composed['district_name'] = address['administrative_area_level_1'][length]
        if not localized and 'country' in address and isinstance(address['country'], dict):
            composed['country'] = address['country'][length]

        return composed

    def get_country_code(self):
        try:
            return self.address_components.filter(types__name='country').first().short_name.lower()
        except (AttributeError):
            return None

    def __str__(self):
        if self.address_line:
            return self.address_line
        return ""
