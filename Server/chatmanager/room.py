class Room:
    def __init__(self, address, alias, name):
        self._name = name  # roomName
        self._alias_list = list()
        self._address_list = list()
        self._user_count = 0
        self.add_user(address, alias)

    def add_user(self, address, alias):
        # Adds user to room
        if address in self._address_list or alias in self._alias_list:
             return False

        self._address_list.append(address)
        self._alias_list.append(alias)
        self._user_count += 1
        return True

    def remove_user(self, address, alias):
        # Only deletes first instance of alias and address, doesn't check duplicates
        if address in self._address_list and alias in self._alias_list:
            self._address_list.remove(address)
            self._alias_list.remove(alias)
            self._user_count -= 1
            return True

        return False

    def remove_user_by_address(self, address):
        i = self._address_list.index(address)
        self._address_list.remove(address)
        alias = self._alias_list[i]
        del self._alias_list[i]
        self._user_count -= 1
        return alias

    def address_in_room(self, address):
        if address in self._address_list:
            return True
        return False

    def get_name(self):
        return self._name

    def get_address_list(self):
        return self._address_list

    def get_alias_list(self):
        return self._alias_list

    def is_empty(self):
        return self._user_count == 0