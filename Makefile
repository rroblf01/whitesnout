.PHONY: build test shell clean

build:
	docker build -t whitesnout-dev .
	docker run --rm -v $(PWD):/app -w /app whitesnout-dev \
		sh -c "uv sync --dev"

test:
	docker run --rm -v $(PWD):/app -w /app whitesnout-dev uv run pytest -v

shell:
	docker run --rm -it -v $(PWD):/app -w /app whitesnout-dev bash

release:
	docker run --rm -v $(PWD):/app -w /app whitesnout-dev \
		sh -c "maturin build --release --out dist/"

clean:
	docker rmi whitesnout-dev 2>/dev/null || true
	rm -rf target/ dist/ 2>/dev/null || true
