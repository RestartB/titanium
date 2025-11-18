data "external_schema" "sqlalchemy" {
    program = [
        "uv",
        "run",
        "python",
        "-m",
        "lib.sql.atlas"
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