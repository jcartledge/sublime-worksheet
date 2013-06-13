# Sublime Worksheet

This is a Sublime Text 2 plugin for Mac OS X and Linux which passes the contents of a buffer line-by-line to a REPL and displays the results inline.

![a](docs/worksheet.gif)

It's great for trying things out directly in Sublime Text.

**Please note: this plugin does not work on Windows.** See [this issue](https://github.com/jcartledge/sublime-worksheet/issues/12) for more information.

## Languages

Sublime worksheet currently supports the following languages:

 - JavaScript (using the NodeJS REPL)
 - PHP
 - Python
 - Ruby
 - Scala (still a bit buggy)

Sublime Worksheet uses the interpreters that are available on your system. This means that, for example, you need the IRB executable installed and on your path in order to evaluate Ruby worksheets. If you can run a REPL from the command line then the plugin should have no problem running it.

## Install

### Package Control

Sublime Worksheet isn't available in Package Control yet, but it should be soon. In the meantime you'll have to install it manually using one of the methods below:

### Using Git

Go to your SublimeText 2 `Packages` directory and clone the repository using the command below:

`$ git clone https://github.com/jcartledge/sublime-worksheet.git`

### Download Manually

Download the files using the .zip download option.  
Unzip the files.  
Copy the folder to your SublimeText 2 Packages directory.

## Usage

Sublime Worksheet provides a single command, `Evaluate worksheet`, which you can access from the command palette (<kbd>CMD-SHIFT-P</kbd> / <kbd>CTRL-SHIFT-P</kbd>).

The syntax setting of the current document is used to determine which interpreter to run, so make sure this is set correctly.

You don't need to save the document before running `Evaluate worksheet`, but if it has been saved then imports/requires/includes relative to the file should work.

Any errors or timeouts will cause evaluation to stop and the error to be writtn to the document. A timeout occurs if the REPL hasn't returned a result for an evaluated line after 10 seconds.

## Contributing

Please feel free. More REPLs would be great - take a look at [worksheet.sublime-settings](worksheet.sublime-settings) for details of how these are implemented.



