import uuid


def is_valid_uuid(uuid_to_test, version=4):
    # https://stackoverflow.com/a/33245493
    try:
        uuid_obj = uuid.UUID(uuid_to_test, version=version)
    except ValueError:
        return False
    return str(uuid_obj) == uuid_to_test
