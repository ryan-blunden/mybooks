#!/usr/bin/env just

set shell := ["bash", "-c"]

default:
    @just --list


#####################
# LOCAL DEVELOPMENT #
#####################

dev-venv:
    -rm -fr .venv
    uv venv
    just dev-dependencies

dev-dependencies:
    uv sync --all-groups --compile-bytecode

env-file:
    doppler secrets download --no-file --format docker > .env

dev-get-tls:
	doppler secrets get TLS_CERT --plain > tls/cert.pem
	doppler secrets get TLS_KEY --plain > tls/key.pem    

dev-server:
    uv run manage.py runserver_plus [::]:8080

dev-mail:
    npx maildev --smtp 1025 --web 1080 --ip 0.0.0.0
    @open http://localhost:1080 || true


#######
# APP #
#######

app-install-dependencies:
    uv sync --compile-bytecode
    uv lock
    # rm -fr hallite_configurator.egg-info build

app-upgrade-dependencies:
    uv lock --upgrade

pre-commit:
    uv run pre-commit run --all-files

app-dump-data app model:
    uv run manage.py dumpdata {{app}}.{{model}} --format=yaml --indent=2 > {{app}}/fixtures/{{model}}.yaml

app-api-spec:
    @echo "Generating OpenAPI specification..."
    uv run manage.py spectacular --file openapi.yaml --format openapi
    @echo "API spec saved to openapi.yaml"


app-ngrok:
    ngrok http --url mybooks.ngrok.app 8080

app-collectstatic:
   uv run manage.py tailwind build
   uv run manage.py collectstatic --no-input -i node_modules -i source.css

agent-run:
    doppler run --config dev_agent -- streamlit run agent/agent.py --server.port 9090 --logger.level info --server.headless true

agent-ngrok:
    ngrok http --url mybooks-agent.ngrok.app 9090

##########
# CHECKS #
##########

check:
    uv run just check-black
    uv run just check-isort
    uv run just check-flake8
    uv run just check-pylint
    # uv run just check-djhtml
    uv run just check-js-css
    uv run just check-autoflake
    uv run just check-types

check-djlint:
    uv run djlint ./ --check

check-flake8:
    uv run flake8 ./

check-isort:
    uv run isort ./ --check

check-black:
    uv run black ./ --check

check-dockerfile:
    docker run --rm -i hadolint/hadolint hadolint - < "Dockerfile"

check-pylint:
    uv run pylint --load-plugins pylint_django ./

# check-djhtml:
#     uv run djhtml mybooks templates -c

check-js-css:
    cd mybooks/static/mybooks && npm run lint-fix

check-autoflake:
    uv run autoflake --check --quiet --recursive ./

check-types:
    uv run ty check


##########
# FORMAT #
##########

format:
    uv run just format-black
    uv run just format-isort
    # uv run just format-djhtml
    # uv run just format-js-css
    uv run just format-autoflake
    just format-whitespace

format-isort:
    uv run isort ./

format-black:
    uv run black ./

# format-djhtml:
#     uv run djhtml core config templates

# format-js-css:
#     cd core/static/core && npm run format

format-autoflake:
    uv run autoflake --in-place --recursive ./

format-whitespace:
    find . -name "*.py" -not -path "./.venv/*" -not -path "./node_modules/*" -exec sed -i '' 's/[[:space:]]*$//' {} \;


#########
# TESTS #
#########

test:
    uv run python manage.py test --verbosity=2

test-coverage:
    uv run coverage run --source='.' manage.py test
    uv run coverage report
    uv run coverage html
