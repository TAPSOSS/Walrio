# Contributing to Walrio
Walrio is an free and open-source project, it is possible and encouraged to participate in the development of this music player. You can also participate by answering questions, reporting bugs or helping with documentation. If you plan on submitting any code/modules/documentation updates, make sure to follow the guidelines below.

## Contributing Documentation VS Code
Code must follow the styling requirements below and all parts of the contribution requirements. If you're simply updating documentation on the other hand, all you need to do is fork the repo, change whatever file in the docs folder you want to change while making everything still work and look nice, and then submit a pull requrest with your documented change. The styling requirements and most of the contribution requirements are written with code contribution in mind and can be ignored for documentation.

## Styling REQUIREMENTS
No emojis are allowed in any form of code. They're allowed in documentation/GUIs/READMEs/author names, but not any of the modules. Also every function needs a minimum of a 1-line comment explaining what it does right above under its declaration with sphinx-supported autodoc formatting (w/ napoleon support). Any paramters or return values MUST be explained. Generally this means something like:
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

### Module Documentation Requirements
For command-line tools in any `modules/` subfolder (`core/`, `addons/`, and `niche/`), ensure your `--help` output is comprehensive with clear descriptions and examples (see [convert.py](/modules/addons/convert.py)). The documentation will be automatically generated from the help text you've written so make sure to include all tags and a few example commands if possible/needed.

Here's an example of good CLI help documentation structure:

```
Examples:
  # Organize music library using default format: album/albumartist
  python organize.py /path/to/music/library /path/to/organized/library

  # Custom folder format with year and genre
  python organize.py /music /organized --folder-format "{year}/{genre}/{albumartist}/{album}"

  # Artist-based organization
  python organize.py /music /organized --folder-format "{artist}/{album}"

  # Detailed organization with track info
  python organize.py /music /organized --folder-format "{albumartist}/{year} - {album}"

Available pre-defined metadata fields:
  {title}       - Song title (searches: title, Title, TITLE, TIT2, etc.)
  {album}       - Album name (searches: album, Album, ALBUM, TALB, etc.)
  {artist}      - Track artist (searches: artist, Artist, TPE1, etc.)
  {albumartist} - Album artist (searches: albumartist, AlbumArtist, TPE2, etc.)
  {track}       - Track number (searches: track, Track, tracknumber, etc.)
  {year}        - Release year (searches: year, Year, date, Date, etc.)
  {genre}       - Music genre (searches: genre, Genre, GENRE, etc.)
  {disc}        - Disc number (searches: disc, Disc, discnumber, etc.)
  {composer}    - Composer (searches: composer, Composer, TCOM, etc.)
  {comment}     - Comment field (searches: comment, Comment, COMM, etc.)

You can also use any raw metadata tag name (case-sensitive):
  {ARTIST}      - Use exact tag name from file
  {TPE1}        - Use ID3v2 tag directly
  {Custom_Tag}  - Use any custom tag present in the file

Character replacement examples (default: problematic chars become safe alternatives):
  --replace-char "/" "-"             # Replace forward slashes with dashes (default)
  --rc ":" "-"                       # Replace colons with dashes (default, using shortcut)
  --replace-char "&" "and"           # Replace ampersands with 'and'
  --rc "/" "-" --rc "&" "and"        # Multiple replacements using shortcuts
  --replace-char "?" ""              # Remove question marks (replace with nothing)
  --dontreplace --rc "/" "-"         # Disable defaults, only replace / with -
  --dr --rc "=" "_"                  # Disable defaults using shortcut, replace = with _

Sanitization examples (default: sanitize enabled with conservative character set):
  --sanitize                         # Explicitly enable character filtering (default behavior)
  --s                                # Same as above using shortcut
  --dont-sanitize                    # Disable character filtering, keep all characters
  --ds                               # Same as above using shortcut
  --ds --rc "/" "-"                  # No filtering, but still replace / with -
  --dont-sanitize --dontreplace      # No filtering or replacements at all
  --s --rc "&" "and"                 # Explicit sanitize with custom replacements
  --custom-sanitize "abcABC123-_ "   # Use custom allowed character set
  --cs "0123456789"                  # Only allow numbers using shortcut

Custom sanitization examples:
  --cs "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_ "  # Basic set
  --cs "abcABC123[]()-_~@=+ "        # Include brackets and symbols (may cause issues)
  --custom-sanitize "αβγδεζηθικλμνξοπρστυφχψω"  # Greek letters only
  --cs "あいうえおかきくけこ"              # Japanese characters

Folder format tips:
  - Use forward slashes (/) to separate folder levels: "{artist}/{album}"
  - Missing fields will be empty (logged as warnings)
  - Use --skip-no-metadata to skip files missing critical metadata
  - Character replacements are applied before sanitization
  - When sanitization is enabled, problematic characters are removed/replaced
  - Default character set excludes apostrophes and special chars for music player compatibility
```

This creates comprehensive help with usage examples, detailed field explanations, and helpful tips that users need.

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
"""
```

4. For any new files, make sure they're added to the auto-generated sphinx documentation (check the docs folder and for examples like [this](/docs/source/api/player.rst)), add any newly needed imports to [requirements.txt](requirements.txt), and add your name to the [authors](AUTHORS) file if you want to (not required). For CLI tools in any `modules/` subfolder (`core/`, `addons/`, `niche/`, etc.), make sure your `--help` output is good quality as it will be used to auto-generate user documentation.

5. Once the code, documentation, and headers are all set properly, send a [pull request](https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/proposing-changes-to-your-work-with-pull-requests/creating-a-pull-request) in for code review. Styling for this pull request should be automatically filled in by GitHub and you just need to fill in the template and change the pull request title to one of the 3 given to submit the pull request. Relevant feedback will be given both through automatede tests and direct human communication or the pull request will be accepted and your changes/new code will be part of Walrio repository.

## Questions?

If you have questions about contributing:
- Open an issue for discussion
- Check existing issues and pull requests
- Review this contributing guide

## License

By contributing to Walrio, you agree that your contributions will be licensed under the same license as the project.

Thank you for contributing to Walrio! 🎵