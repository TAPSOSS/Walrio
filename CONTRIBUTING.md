# Contributing to Walrio

Walrio is an free and open-source project, it is possible and encouraged to participate in the development of this music player. You can also participate by answering questions, reporting bugs or helping with documentation. If you plan on submitting any code/modules/documentation updates, please try to follow the commit message and pull request styling used by recent commits until guidelines have been added here for those things.

At the moment all that is required code-wise is for each function to have a minimum of a 1-line comment explaining its function in any module and what any arguments/parameters do, and for files outside of the GUI files to be written in Python. 

Once more progress has been done this guide will be updated and documentation for what currently exits will be provided in order to make the contribution process easier.

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
4. Add documentation (currently not needed, but will be updated/explained once documentation is done better). At the moment all you need to do is add a 1-line description and your new file name to the README.md.
5. Once the code, documentation, and headers are all set properly, send a [pull request](https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/proposing-changes-to-your-work-with-pull-requests/creating-a-pull-request) in for code review. Make sure the title of your pull request explicitely says which file(s) you created/altered such as "Added Library Analyzer: audio_library.py". If you are bug fixing multiple files please try to seperate out the bug fixes/pull requests, but if you need to do them all at once just say "Bug Fix: Multiple Files" and then list the relevent files in the pull request description. Relevant feedback will be given or the pull request will be accepted and your changes/new code will be part of Walrio repository.

## Questions?

If you have questions about contributing:
- Open an issue for discussion
- Check existing issues and pull requests
- Review this contributing guide

## License

By contributing to Walrio, you agree that your contributions will be licensed under the same license as the project.

Thank you for contributing to Walrio! 🎵