VERSION := $(shell sed -n 's/^version = "\([^"]*\)"/\1/p' pyproject.toml)

tag:
	# Create a new tag
	git tag -a "v$(VERSION)" -m "version++ (v$(VERSION))" && \
	git push origin "v$(VERSION)"

release: tag dist
	# Create a new GitHub release
	gh release create "v$(VERSION)" \
		--title "v$(VERSION)" \
		--generate-notes
