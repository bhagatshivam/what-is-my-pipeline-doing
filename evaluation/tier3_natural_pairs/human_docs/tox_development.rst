.. Saved verbatim for Tier 3 (Natural-pairs comparison, EVALUATION_PLAN.md
.. Method 8) reproducibility -- source URLs can drift or 404 over time, and
.. this comparison should not depend on them staying live.
..
.. Source: tox-dev/tox, docs/development.rst
.. URL: https://raw.githubusercontent.com/tox-dev/tox/main/docs/development.rst
.. Branch: main
.. Fetched: 2026-08-23
..
.. Corresponds to: tests/fixtures/multi/tox/ -- specifically check.yaml,
.. prepare-release.yaml, and release.yaml. update-schemastore.yaml is not
.. mentioned in this doc.
..
.. Excerpt only -- the "Automated testing" and "Creating a new release"
.. sections are the CI-relevant portions of a much longer document that also
.. covers local setup, running tests, linting, code style, building docs,
.. submitting PRs, changelog entries, and becoming a maintainer (not
.. reproduced here as it isn't CI-specific).

Automated testing
=================

All pull requests and merges to the ``main`` branch are tested using :gh:`GitHub Actions <features/actions>` (configured
by ``check.yaml`` file inside the ``.github/workflows`` directory). You can find the status and the results to the CI
runs for your PR on GitHub's Web UI for the pull request. You can also find links to the CI services' pages for the
specific builds in the form of "Details" links, in case the CI run fails and you wish to view the output.

To trigger CI to run again for a pull request, you can close and open the pull request or submit another change to the
pull request. If needed, project maintainers can manually trigger a restart of a job/build.

Creating a new release
======================

tox supports two methods for preparing releases:

Method 1: Local release (requires git access)
---------------------------------------------

.. code-block:: shell

    tox r -e release -- <version>

Example:

.. code-block:: shell

    tox r -e release -- 4.27.0

This will:

1. Create a ``release-<version>`` branch from upstream/main.
2. Generate changelog using towncrier.
3. Commit changes with message "release <version>".
4. Tag the commit with the version number.
5. Force-push to main and push the tag.
6. Clean up local branches.

Requirements:

- Write access to tox-dev/tox repository.
- Configured git remote pointing to tox-dev/tox (typically named ``upstream``).

  .. code-block:: shell

      git remote add upstream git@github.com:tox-dev/tox.git

- Local dependencies installed via tox.

Method 2: GitHub Actions workflow dispatch
------------------------------------------

Navigate to `Actions > Prepare Release <https://github.com/tox-dev/tox/actions/workflows/prepare-release.yaml>`_ and:

1. Click "Run workflow".
2. Select the branch (usually ``main``).
3. Choose the version bump type:

   - ``auto`` (default) - Automatically bump minor if feature changelogs exist, otherwise bump patch.
   - ``major`` - Bump major version (e.g., 4.0.0 → 5.0.0).
   - ``minor`` - Bump minor version (e.g., 4.27.0 → 4.28.0).
   - ``patch`` - Bump patch version (e.g., 4.27.0 → 4.27.1).

4. Click "Run workflow".

The workflow executes the same ``tasks/release.py`` script in a clean CI environment.

Requirements:

- Write access to tox-dev/tox repository (workflow permissions).
- For repositories with branch protection on ``main``, a ``RELEASE_PAT`` secret must be configured in the
  ``release-auth`` environment with a fine-grained Personal Access Token that has permissions to bypass branch
  protection rules.
- Maintainer approval is required to trigger the workflow (configured via environment protection rules).

After release preparation
-------------------------

Both methods push a tag to the repository. The tag push automatically triggers the ``release.yaml`` workflow which:

1. Builds Python packages (sdist + wheel).
2. Publishes to PyPI via trusted publishing.

.. note::

    - Both methods force-push to main (ensure no concurrent work).
    - The release process is atomic and should not be interrupted.
    - Failed releases can be retried with the same version number.
