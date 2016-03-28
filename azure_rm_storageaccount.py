#!/usr/bin/python
#
# (c) 2016 Matt Davis, <mdavis@redhat.com>
#          Chris Houseknecht, <house@redhat.com>
#
# This file is part of Ansible
#
# Ansible is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Ansible is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Ansible.  If not, see <http://www.gnu.org/licenses/>.
#


# normally we'd put this at the bottom to preserve line numbers, but we can't use a forward-defined base class
# without playing games with __metaclass__ or runtime base type hackery.
# TODO: figure out a better way...
from ansible.module_utils.basic import *
from ansible.module_utils.azure_rm_common import *

try:
    from msrestazure.azure_exceptions import CloudError
    from azure.storage.cloudstorageaccount import CloudStorageAccount
    from azure.common import AzureMissingResourceHttpError, AzureHttpError
    from azure.mgmt.storage.models import AccountType,\
                                          AccountStatus, \
                                          ProvisioningState, \
                                          StorageAccountUpdateParameters,\
                                          CustomDomain, StorageAccountCreateParameters, KeyName
except ImportError:
    # This is handled in azure_rm_common
    pass


DOCUMENTATION = '''
---
module: azure_rm_storageaccount

short_description: Manage Azure storage accounts.

description:
    - Create, update and delete storage accounts within a given resource group.
    - For authentication with Azure you can pass parameters, set environment variables or use a profile stored
      in ~/.azure/credentials. Authentication is possible using a service principal or Active Directory user.
    - To authenticate via service principal pass subscription_id, client_id, secret and tenant or set set environment
      variables AZURE_SUBSCRIPTION_ID, AZURE_CLIENT_ID, AZURE_SECRET and AZURE_TENANT.
    - To Authentication via Active Directory user pass ad_user and password, or set AZURE_AD_USER and
      AZURE_PASSWORD in the environment.
    - Alternatively, credentials can be stored in ~/.azure/credentials. This is an ini file containing
      a [default] section and the following keys: subscription_id, client_id, secret and tenant or
      ad_user and password. It is also possible to add addition profiles to this file. Specify the profile
      by passing profile or setting AZURE_PROFILE in the environment.

options:
    profile:
        description:
            - security profile found in ~/.azure/credentials file
        required: false
        default: null
    subscription_id:
        description:
            - Azure subscription Id that owns the resource group and storage accounts.
        required: false
        default: null
    client_id:
        description:
            - Azure client_id used for authentication.
        required: false
        default: null
    secret:
        description:
            - Azure client_secrent used for authentication.
        required: false
        default: null
    tenant:
        description:
            - Azure tenant_id used for authentication.
        required: false
        default: null
    resource_group:
        description:
            - name of resource group.
        required: true
        default: null
    name:
        description:
            - name of the storage account.
        default: null
    state:
        description:
            - Assert the state of the storage account. Use 'present' to create or update a storage account and
              'absent' to delete an account.
        required: false
        default: present
        choices:
            - absent
            - present
    location:
        description:
            - Valid azure location. Defaults to location of the resource group.
        default: resource_group location
    account_type:
        description:
            - type of storage account. Can be one of 'Premium_LRS', 'Standard_GRS', 'Standard_LRS', 'Standard_RAGRS',
              'Standard_ZRS'. Required when creating a storage account. Note that StandardZRS and PremiumLRS accounts cannot be
              changed to other account types, and other account types cannot be changed to StandardZRS or PremiumLRS.
        required: false
        default: null
    custom_domain:
        description:
            - User domain assigned to the storage account. Must be a dictionary with 'name' and 'use_sub_domain' keys where 'name' 
              is the CNAME source. Only one custom domain is supported per storage account at this time. To clear the existing custom 
              domain, use an empty string for the custom domain name property.
            - Can be added to an existing storage account. Will be ignored during storage account creation.
        required: false
        default: null
    tags:
        description:
            - Dictionary of string:string pairs to assign as metadata to the object. Treated as the explicit metadata
              for the object. In other words, existing metadata will be replaced with provided values. If no values
              provided, existing metadata will be removed.
        required: false
        default: null
requirements:
    - "python >= 2.7"
    - "azure >= 2.0.0"

authors:
    - "Chris Houseknecht house@redhat.com"
    - "Matt Davis mdavis@redhat.com"
'''
EXAMPLES = '''
    - name: remove account, if it exists
      azure_rm_storageaccount:
        resource_group: Testing
        location: 'East US 2'
        name: clh0002
        state: absent

    - name: create an account
      azure_rm_storageaccount:
        resource_group: Testing
        location: 'East US 2'
        name: clh0002
        type: Standard_RAGRS
'''

RETURNS = '''
{
    "changed": true,
    "check_mode": false,
    "results": {
        "account_type": "Standard_RAGRS",
        "custom_domain": null,
        "id": "/subscriptions/3f7e29ba-24e0-42f6-8d9c-5149a14bda37/resourceGroups/testing/providers/Microsoft.Storage/storageAccounts/clh0003",
        "location": "eastus2",
        "name": "clh0003",
        "primary_endpoints": {
            "blob": "https://clh0003.blob.core.windows.net/",
            "queue": "https://clh0003.queue.core.windows.net/",
            "table": "https://clh0003.table.core.windows.net/"
        },
        "primary_location": "eastus2",
        "provisioning_state": "Succeeded",
        "resource_group": "Testing",
        "secondary_endpoints": {
            "blob": "https://clh0003-secondary.blob.core.windows.net/",
            "queue": "https://clh0003-secondary.queue.core.windows.net/",
            "table": "https://clh0003-secondary.table.core.windows.net/"
        },
        "secondary_location": "centralus",
        "status_of_primary": "Available",
        "status_of_secondary": "Available",
        "tags": null,
        "type": "Microsoft.Storage/storageAccounts"
    }
}

'''

NAME_PATTERN = re.compile(r"^[a-z0-9]+$")


class AzureRMStorageAccount(AzureRMModuleBase):

    def __init__(self, **kwargs):

        self.module_arg_spec = dict(
            account_type=dict(type='str', choices=[], aliases=['type']),
            custom_domain=dict(type='dict'),
            force=dict(type='bool', default=False),
            location=dict(type='str'),
            name=dict(type='str', required=True),
            resource_group=dict(required=True, type='str'),
            state=dict(default='present', choices=['present', 'absent']),
            tags=dict(type='dict'),
            log_path=dict(type='str', default='azure_rm_storageaccount.log')
        )

        for key in AccountType:
            self.module_arg_spec['account_type']['choices'].append(getattr(key, 'value'))

        super(AzureRMStorageAccount, self).__init__(self.module_arg_spec,
                                                    supports_check_mode=True,
                                                    **kwargs)
        self.results = dict(
            changed=False,
            check_mode=self.check_mode
        )

        self.account_dict = None
        self.resource_group = None
        self.name = None
        self.state = None
        self.location = None
        self.account_type = None
        self.custom_domain = None
        self.tags = None

    def exec_module_impl(self, **kwargs):

        for key in self.module_arg_spec:
            setattr(self, key, kwargs[key])

        resource_group = self.get_resource_group(self.resource_group)
        if not self.location:
            # Set default location
            self.location = resource_group.location

        if not NAME_PATTERN.match(self.name):
            self.fail("Parameter error: name must contain numbers and lowercase letters only.")

        if len(self.name) < 3 or len(self.name) > 24:
            self.fail("Parameter error: name length must be between 3 and 24 characters.")

        if self.custom_domain:
            if self.custom_domain.get('name', None) is None:
                self.fail("Parameter error: expecting custom_domain to have a name attribute of type string.")
            if self.custom_domain.get('use_sub_domain', None) is None:
                self.fail("Parameter error: expecting custom_domain to have a use_sub_domain "
                          "attribute of type boolean.")

        self.account_dict = self.get_account()

        if self.account_dict and self.account_dict['provisioning_state'] != AZURE_SUCCESS_STATE :
            self.fail("Error: storage account {0} has not completed provisioning. State is {1}. Expecting state "
                      "to be {2}.".format(self.name, self.account_dict['provisioning_state'], AZURE_SUCCESS_STATE))

        if self.account_dict is not None:
            self.results['results'] = self.account_dict
        else:
            self.results['results'] = dict()

        if self.state == 'present':
            if not self.account_dict:
                self.results['results'] = self.create_account()
            else:
                self.update_account()
        elif self.state == 'absent':
            if self.account_dict:
                self.delete_account()
                self.results['results'] = dict(Status='Deleted')
        return self.results

    def check_name_availability(self):
        try:
            response = self.storage_client.storage_accounts.check_name_availability(self.name)
        except AzureHttpError, e:
            self.log('Error attempting to validate name.')
            self.fail("Error checking name availability: {0}".format(str(e)))

        if not response.name_available:
            self.log('Error name not available.')
            self.fail("{0} - {1}".format(response.message, response.reason))

    def get_account(self):
        self.log('Get properties for account {0}'.format(self.name))
        account_obj = None
        account_dict = None

        try:
            account_obj = self.storage_client.storage_accounts.get_properties(self.resource_group, self.name)
        except CloudError, exc:
            pass

        if account_obj:
            account_dict = self.account_obj_to_dict(account_obj)

        return account_dict

    def account_obj_to_dict(self, account_obj):
        account_dict = dict(
            id=account_obj.id,
            name=account_obj.name,
            location=account_obj.location,
            resource_group=self.resource_group,
            type=account_obj.type,
            account_type=account_obj.account_type.value,
            provisioning_state=account_obj.provisioning_state.value,
            secondary_location=account_obj.secondary_location,
            status_of_primary=(account_obj.status_of_primary.value
                               if account_obj.status_of_primary is not None else None),
            status_of_secondary=(account_obj.status_of_secondary.value
                                 if account_obj.status_of_secondary is not None else None),
            primary_location=account_obj.primary_location
        )
        account_dict['custom_domain'] = None
        if account_obj.custom_domain:
            account_dict['custom_domain'] = dict(
                name=account_obj.custom_domain.name,
                use_sub_domain=account_obj.custom_domain.use_sub_domain
            )

        account_dict['primary_endpoints'] = None
        if account_obj.primary_endpoints:
            account_dict['primary_endpoints'] = dict(
                blob=account_obj.primary_endpoints.blob,
                queue=account_obj.primary_endpoints.queue,
                table=account_obj.primary_endpoints.table
            )
        account_dict['secondary_endpoints'] = None
        if account_obj.secondary_endpoints:
            account_dict['secondary_endpoints'] = dict(
                blob=account_obj.secondary_endpoints.blob,
                queue=account_obj.secondary_endpoints.queue,
                table=account_obj.secondary_endpoints.table
            )
        account_dict['tags'] = None
        if account_obj.tags:
            account_dict['tags'] = account_obj.tags
        return account_dict

    def update_account(self):
        self.log('Update storage account {0}'.format(self.name))
        if self.account_type:
            if self.account_type != self.account_dict['account_type']:
                # change the account type
                if self.account_dict['account_type'] in [AccountType.premium_lrs, AccountType.standard_zrs]:
                    self.fail("Storage accounts of type {0} and {1} cannot be changed.".format(
                        AccountType.premium_lrs, AccountType.standard_zrs))
                if self.account_type in [AccountType.premium_lrs, AccountType.standard_zrs]:
                    self.fail("Storage account of type {0} cannot be changed to a type of {1} or {2}.".format(
                        self.account_dict['account_type'], AccountType.premium_lrs, AccountType.standard_zrs))
                self.results['changed'] = True
                self.account_dict['account_type'] = self.account_type

                if self.results['changed'] and not self.check_mode:
                    # Perform the update. The API only allows changing one attribute per call.
                    try:
                        parameters = StorageAccountUpdateParameters(account_type=self.account_dict['account_type'])
                        self.storage_client.storage_accounts.update(self.resource_group,
                                                                    self.name,
                                                                    parameters)
                    except AzureHttpError, e:
                        self.fail("Failed to update account type: {0}".format(str(e)))
                    except CloudError, e:
                        self.fail("Failed to update account type: {0}".format(str(e)))

        if self.custom_domain:
            if not self.account_dict['custom_domain'] or \
               self.account_dict['custom_domain'] != self.account_dict['custom_domain']:
                self.results['changed'] = True
                self.account_dict['custom_domain'] = self.custom_domain

            if self.results['changed'] and not self.check_mode:
                new_domain = CustomDomain(name=self.custom_domain['name'],
                                          use_sub_domain=self.custom_domain['use_sub_domain'])
                parameters = StorageAccountUpdateParameters(custom_domain=new_domain)
                try:
                    self.storage_client.storage_accounts.update(self.resource_group, self.name, parameters)
                except AzureHttpError, e:
                    self.fail("Failed to update custom domain: {0}".format(str(e)))
                except CloudError, e:
                    self.fail("Failed to update custom domain: {0}".format(str(e)))

        if self.tags:
            if self.account_dict['tags'] != self.tags:
                self.results['changed'] = True
                self.account_dict['tags'] = self.tags

            if self.results['changed'] and not self.check_mode:
                parameters = StorageAccountUpdateParameters(tags=self.account_dict['tags'])
                try:
                    self.storage_client.storage_accounts.update(self.resource_group, self.name, parameters)
                except AzureHttpError, e:
                    self.fail("Failed to update tags: {0}".format(str(e)))
                except CloudError, e:
                    self.fail("Failed to update tags: {0}".format(str(e)))

    def create_account(self):
        self.log("Creating account {0}".format(self.name))

        if not self.location:
            self.fail('Parameter error: location required when creating a storage account.')

        if not self.account_type:
            self.fail('Parameter error: account_type required when creating a storage account.')

        self.check_name_availability()
        self.results['changed'] = True

        if self.check_mode:
            account_dict = dict(
                location=self.location,
                account_type=self.account_type,
                name=self.name,
                resource_group=self.resource_group,
                tags=dict()
            )
            if self.tags:
                account_dict['tags'] = self.tags
            return account_dict

        try:
            parameters = StorageAccountCreateParameters(account_type=self.account_type, location=self.location,
                                                        tags=self.tags)
            poller = self.storage_client.storage_accounts.create(self.resource_group, self.name, parameters)
        except AzureHttpError, e:
            self.log('Error creating storage account.')
            self.fail("Failed to create account: {0}".format(str(e)))

        self.get_poller_result(poller)
        # the poller doesn't actually return anything
        return self.get_account()

    def delete_account(self):
        if self.account_dict['provisioning_state'] != ProvisioningState.succeeded.value:
            self.fail("Account provisioning has not completed. State is: {0}".format(
                self.account_dict['provisioning_state']))

        if self.account_dict['provisioning_state'] == ProvisioningState.succeeded.value and \
           self.account_has_blob_containers() and not self.force:
            self.fail("Account contains blob containers. Is it in use? Use the force option to attempt deletion.")

        self.log('Delete storage account {0}'.format(self.name))
        self.results['changed'] = True
        if not self.check_mode:
            try:
                status = self.storage_client.storage_accounts.delete(self.resource_group, self.name)
                self.log("delete status: ")
                self.log(str(status))
            except AzureHttpError, e:
                self.fail("Failed to delete the account: {0}".format(str(e)))
        return True

    def account_has_blob_containers(self):
        '''
        If there are blob containers, then there are likely VMs depending on this account and it should
        not be deleted.
        '''
        self.log('Checking for existing blob containers')
        keys = dict()
        try:
            # Get keys from the storage account
            account_keys = self.storage_client.storage_accounts.list_keys(self.resource_group, self.name)
            keys['key1'] = account_keys.key1
            keys['key2'] = account_keys.key2
        except AzureHttpError, e:
            self.log("Error getting keys for account {0}".format(e))
            self.fail("check_for_container:Failed to get account keys: {0}".format(e))

        try:
            cloud_storage = CloudStorageAccount(self.name, keys['key1']).create_page_blob_service()
        except Exception, e:
            self.log("Error creating blob service: {0}".format(e))
            self.fail("check_for_container:Error creating blob service: {0}".format(e))

        try:
            response = cloud_storage.list_containers()
        except AzureMissingResourceHttpError:
            # No blob storage available?
            return False

        if len(response.items) > 0:
            return True
        return False


def main():
    if '--interactive' in sys.argv:
        # import the module here so we can reset the default complex args value
        import ansible.module_utils.basic

        ansible.module_utils.basic.MODULE_COMPLEX_ARGS = json.dumps(dict(
            name='mdavis12341',
            resource_group="rm_demo",
            state='absent',
            location='West US',
            account_type="Premium_LRS",

            log_mode='stderr',
            #filter_logger=False,
        ))

    AzureRMStorageAccount().exec_module()

if __name__ == '__main__':
    main()
