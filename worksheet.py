import sublime
import sublime_plugin
import repl


class WorksheetCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        self.repl = self.get_repl()
        if self.repl is not None:
            self.remove_previous_results()
            self.repl.correspond('')
            self.process_line(0)

    def get_repl(self):
        settings = sublime.load_settings("worksheet.sublime-settings")
        languages = settings.get('worksheet_languages')
        language = self.get_language()
        if language in languages:
            repl_settings = languages.get(language)
            args = repl_settings.get('args')
            del repl_settings['args']
            return repl.Repl(args, **repl_settings)
        else:
            sublime.error_message('No worksheet REPL found for ' + language)

    def get_language(self):
        return self.view.settings().get('syntax').split('/')[-1].split('.')[0]

    def remove_previous_results(self):
        view = self.view
        edit = view.begin_edit('remove_previous_results')
        for region in reversed(view.find_all("^" + self.repl.prefix)):
            view.erase(edit, view.full_line(region))
        self.view.end_edit(edit)

    def process_line(self, start):
        view = self.view
        line = view.full_line(start)
        next_start = line.end()
        line_text = view.substr(line)
        is_last_line = "\n" not in line_text
        if is_last_line:                        # this doesn't actually work
            next_start += 1
            line_text += "\n"
        thread = repl.ReplThread(self.repl, line_text)
        self.queue_thread(thread, next_start, is_last_line)
        self.set_status('Sending 1 line to %(language)s REPL.')
        thread.start()

    def queue_thread(self, thread, start, is_last_line):
        sublime.set_timeout(
            lambda: self.handle_thread(thread, start, is_last_line),
            100
        )

    def handle_thread(self, thread, next_start, is_last_line):
        if thread.is_alive():
            self.set_status('Waiting for %(language)s REPL.')
            self.queue_thread(thread, next_start, is_last_line)
        else:
            self.set_status('')
            edit = self.view.begin_edit('process_line')
            self.view.insert(edit, next_start, thread.result)
            self.view.end_edit(edit)
            next_start += len(thread.result)
            if not is_last_line:
                self.process_line(next_start)

    def set_status(self, msg, key='worksheet'):
        self.view.set_status(key, msg % {'language': self.get_language()})
