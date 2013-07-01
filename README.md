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

Sublime Worksheet provides two commands which you can access from the command palette (<kbd>CMD-SHIFT-P</kbd> / <kbd>CTRL-SHIFT-P</kbd>):

### `Worksheet: Evaluate worksheet`

Passes the contents of the current document line by line to the interpreter which matches its syntax setting.

Results are inserted as comments directly below the statement, as they would appear if you were entering them in the REPL.

This automatically clears the results of previous evaluations first.

You don't need to save the document before running `Evaluate worksheet`, but if it has been saved then you can write imports/requires/includes relative to the file and they should work.

Any errors or timeouts will cause evaluation to stop and the error to be written to the document. A timeout occurs if the REPL hasn't returned a result for an evaluated line after 10 seconds.

### `Worksheet: Clear worksheet results`

Removes comments inserted by evaluating the worksheet.

## Contributing

Please feel free. More REPLs would be great - take a look at [worksheet.sublime-settings](worksheet.sublime-settings) for details of how these are implemented.



