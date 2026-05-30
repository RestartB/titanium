import logging


def return_ctrlguild():
    # Set up reader
    import configparser

    config = configparser.RawConfigParser()

    # Read path section of config file, add it to dict
    try:
        config.read("config.cfg")
        options_dict = dict(config.items("OPTIONS"))
    except Exception:
        logging.error(
            "[INIT] Config file malformed: Error while reading Options section! The file may be missing or malformed."
        )

    # Config File Vars
    return int(options_dict["control-guild"])
