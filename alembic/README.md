**Whenever te DB schema is changed, we need to update the current DB, to reflect the changes without loosing the current data stored in DB.**

To do this, we use `alembic`.

---

## Installation

`alembic` is set as an optional dependency of `clothion`. Just install it with :

```console
pip install -e .[admin]
```

## Usage

### Creating a revision

After updating the DB schema, create a revision in `alembic` :

```console
alembic revision --autogenerate -m "<commit_message>"
```

---

This will generate a migration script in `alembic/versions/<xxx>.py`

### Review the auto-generated migration

You need to check the generated migration script manually, ensuring the changes are applied correctly, and it doesn't mess our DB :)

You might need to change the script manually to ensure the changes are correct.

### Run the migration

Then, run the migration by specifying the revision number. Alternatively, you can ask `alembic` to update to the latest changes by specifying `head` instead :

```console
alembic upgrade head
```

## Others

View the current revision with :

```console
alembic current
```

---

View the history with :

```console
alembic history --verbose
```
