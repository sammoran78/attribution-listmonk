# Docker suite for development

**NOTE**: This exists only for local development. If you're interested in using
Docker for a production setup, visit the
[docs](https://listmonk.app/docs/installation/#docker) instead.

### Objective

The purpose of this Docker suite for local development is to isolate all the dev
dependencies in a Docker environment. The containers have a host volume mounted
inside for the entire app directory. This helps us to not do a full
`docker build` for every single local change, only restarting the Docker
environment is enough.

## Setting up a dev suite

To spin up a local suite of:

- PostgreSQL
- Mailhog
- Node.js frontend app
- Golang backend app

### Verify your config file

The config file provided at `dev/config.toml` will be used when running the
containerized development stack. Make sure the values set within are suitable
for the feature you're trying to develop.

### Setup DB

Running this will build the appropriate images and initialize the database.

```bash
make init-dev-docker
```

### Start frontend and backend apps

Running this start your local development stack.

```bash
make dev-docker
```

Visit `http://localhost:8080` on your browser.

### Subscriber phone numbers

The admin subscriber editor, public signup page, generated embed forms, and
subscriber preferences include an optional phone number. It is stored as a string
in `subscribers.attribs.phone`; no schema migration is needed. Country prefixes,
leading zeroes, spaces, and extensions are preserved. The forms accept up to
64 characters and trim surrounding whitespace.

The admin API accepts it in `attribs`, for example
`{"attribs":{"phone":"+61 412 345 678"}}`. CSV imports and exports carry it in
the existing `attributes` JSON column. The public signup API accepts `phone`
alongside `email` and `name`. As with names, repeat public signups do not replace
an existing subscriber's profile; use the admin editor or subscriber preferences
to change or clear the number. Preference submissions that omit `phone` preserve
the saved number, while an explicitly empty field removes it.

Run the focused checks with `go test ./models` and, from `frontend`,
`node --test tests/subscriber-phone.test.cjs`.

### Tear down

This will tear down all the data, including DB.

```bash
make rm-dev-docker
```

### See local changes in action

- Backend: Anytime you do a change to the Go app, it needs to be compiled. Just
  run `make dev-docker` again and that should automatically handle it for you.
- Frontend: Anytime you change the frontend code, you don't need to do anything.
  Since `yarn` is watching for all the changes and we have mounted the code
  inside the docker container, `yarn` server automatically restarts.
