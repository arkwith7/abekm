import '@testing-library/jest-dom';

const originalConsoleError = console.error;

console.error = (...args: unknown[]) => {
	const firstArg = args[0];
	if (
		typeof firstArg === 'string' &&
		firstArg.includes('ReactDOMTestUtils.act') &&
		firstArg.includes('deprecated')
	) {
		return;
	}

	originalConsoleError(...args);
};
