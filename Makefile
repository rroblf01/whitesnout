.PHONY: build test shell release clean check check-ruff check-ty check-cargo check-fmt

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

check: check-ruff check-ty check-fmt check-cargo

check-ruff:
	uv run ruff check src/ tests/ benchmarks/
	uv run ruff format --check src/ tests/ benchmarks/

check-ty:
	uv run ty check src/ tests/

check-fmt:
	cargo fmt --all --check

check-cargo:
	cargo clippy --all-targets -- -D warnings

clean:
	docker rmi whitesnout-dev 2>/dev/null || true
	rm -rf target/ dist/ 2>/dev/null || true
