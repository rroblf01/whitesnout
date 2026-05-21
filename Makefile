.PHONY: build test shell clean

build:
	docker build -t whitesnout-dev .
	docker run --rm -v $(PWD):/app -w /app whitesnout-dev \
		sh -c "uv sync --dev && maturin develop --uv 2>/dev/null; true"

test:
	docker run --rm -v $(PWD):/app -w /app whitesnout-dev uv run pytest -v

shell:
	docker run --rm -it -v $(PWD):/app -w /app whitesnout-dev bash

clean:
	docker rmi whitesnout-dev 2>/dev/null || true
	rm -rf target/ 2>/dev/null || true
