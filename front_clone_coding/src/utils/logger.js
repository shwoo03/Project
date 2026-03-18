import ora from 'ora';
import chalk from 'chalk';
import { EventEmitter } from 'events';

class Logger extends EventEmitter {
  constructor() {
    super();
    this.spinner = null;
  }

  _emit(type, text) {
    const cleanText = text.replace(/\u001b\[.*?m/g, '');
    this.emit('log', {
      type,
      text: cleanText,
      timestamp: new Date().toISOString(),
    });
  }

  start(message) {
    if (this.spinner) {
      this.spinner.stop();
    }
    this.spinner = ora({ text: message, color: 'cyan' }).start();
    this._emit('start', message);
  }

  succeed(message) {
    if (this.spinner) {
      this.spinner.succeed(chalk.green(message));
      this.spinner = null;
    } else {
      console.log(chalk.green(message));
    }
    this._emit('succeed', message);
  }

  fail(message) {
    if (this.spinner) {
      this.spinner.fail(chalk.red(message));
      this.spinner = null;
    } else {
      console.error(chalk.red(message));
    }
    this._emit('fail', message);
  }

  info(message) {
    if (this.spinner) {
      this.spinner.info(chalk.blue(message));
      this.spinner = null;
    } else {
      console.log(chalk.blue(message));
    }
    this._emit('info', message);
  }

  warn(message) {
    console.log(chalk.yellow(message));
    this._emit('warn', message);
  }

  error(message) {
    console.error(chalk.red(message));
    this._emit('error', message);
  }

  success(message) {
    console.log(chalk.green(message));
    this._emit('success', message);
  }

  debug(message) {
    if (!process.env.DEBUG) return;
    console.log(chalk.gray('[DEBUG]'), chalk.gray(message));
    this._emit('debug', message);
  }

  update(message) {
    if (this.spinner) {
      this.spinner.text = message;
    }
    this._emit('update', message);
  }
}

const logger = new Logger();
export default logger;
