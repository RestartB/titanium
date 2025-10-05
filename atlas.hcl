data "external_schema" "sqlalchemy" {
    program = [
        "atlas-provider-sqlalchemy",
        "--path", "./lib/",
        "--dialect", "postgresql"
    ]
}

env "sqlalchemy" {
    src = data.external_schema.sqlalchemy.url
    dev = "docker://postgres/18/dev?search_path=public"
    migration {
        dir = "file://migrations"
    }
    format {
        migrate {
           diff = "{{ sql . \"  \" }}"
        }
    }
}