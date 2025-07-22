# Contributing to Walrio

Walrio is an free and open-source project, it is possible and encouraged to participate in the development of this music player. You can also participate by answering questions, reporting bugs or helping with documentation. If you plan on submitting any code/modules/documentation updates, make sure to follow the guidelines below.

## Styling REQUIREMENTS
Every function needs a minimum of a 1-line comment explaining what it does right above under its declaration with sphinx-supported autodoc formatting (w/ napoleon support). Generally this means something like:
```
"""
class Greeter:
    """
    A class that greets people.
    """

    def greet(self, name: str) -> str:
        """
        Return a personalized greeting.

        Args:
            name (str): The name to greet.

        Returns:
            str: A greeting string.
        """
        return f"Hi {name}!"
```
^ this would create a doc for 'Greeter' saying that it greets people and 'greet' with the args and return given.

## Styling Suggestions
It would be very much appreciated if the single-line comments in your code follow the style of: ```# (insert comment here)``` (having a space after the #)
as this makes it easier to read them, but unlike autodoc support, this isn't strictly required.

## Contribution REQUIREMENTS
1. To start contributing, first [fork](https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/working-with-forks/fork-a-repo) this respository.

2. Once the repository has been forked, [make a seperate branch](https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/proposing-changes-to-your-work-with-pull-requests/creating-and-deleting-branches-within-your-repository) for each change you plan on making. Please make a seperate branch for each file changed/created if it's possible to do. If files rely on eachother in some way make sure the thing you commit to main first is whatever relies on existing files in the repository to avoid confusion. If you plan on bug fixing an existing file in order to make your new file function, that's fine to include as long as it's mentioned explicitely.

3. Make sure to add this exact header to the top of each file as follows (if creating new files). The code you wrote is still yours and credited to you, just make sure to write your name down in the AUTHORS file if you want a public showcase that you contributed to the project. All commits you made will also show whatever your GitHub name might be. You should also be aware, by the nature of being a BSD 3-Clause project, anyone is free to re-use your code however they want.
```
"""
(Basic summary of function, 5 words max)

Copyright (c) 2025 TAPS OSS
Project: https://github.com/TAPSOSS/Walrio
Licensed under the BSD-3-Clause License (see LICENSE file for details)

(longer description of what the file actually does)
Sample Usage: (include a basic command to test/run the file with)
"""
```

4. Add documentation (will be updated/explained once documentation is done better). At the moment all you need to do is add a 1-line description and add any requirements to the [README.md](README.md) and [requirements.txt](requirements.txt) files and your new file name (with basic description) to the [README.md](README.md) until documentation is standardized.

5. Once the code, documentation, and headers are all set properly, send a [pull request](https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/proposing-changes-to-your-work-with-pull-requests/creating-a-pull-request) in for code review. Styling for this pull request should be automatically filled in by GitHub and you just need to alter the template to submit the pull request. Relevant feedback will be given or the pull request will be accepted and your changes/new code will be part of Walrio repository.

## Questions?

If you have questions about contributing:
- Open an issue for discussion
- Check existing issues and pull requests
- Review this contributing guide

## License

By contributing to Walrio, you agree that your contributions will be licensed under the same license as the project.

Thank you for contributing to Walrio! 🎵