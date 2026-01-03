import React, { act } from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import MessageComposer, { ToolType } from './MessageComposer';

const typeAndSend = async (message: string) => {
  const textbox = screen.getByRole('textbox');

  await act(async () => {
    await userEvent.clear(textbox);
    await userEvent.type(textbox, message);
    await userEvent.click(screen.getByTitle('전송'));
  });
};

describe('MessageComposer', () => {
  test('uses defaultTool and keeps it after sending', async () => {
    const onSendMessage = jest.fn().mockResolvedValue(undefined);

    render(
      <MessageComposer
        onSendMessage={onSendMessage}
        isLoading={false}
        defaultTool={'prior-art' as ToolType}
      />
    );

    await typeAndSend('first');
    await waitFor(() => expect(onSendMessage).toHaveBeenCalledWith('first', [], 'prior-art'));

    await typeAndSend('second');
    await waitFor(() => expect(onSendMessage).toHaveBeenCalledWith('second', [], 'prior-art'));
  });

  test('clears tool after sending when no defaultTool', async () => {
    const onSendMessage = jest.fn().mockResolvedValue(undefined);

    render(<MessageComposer onSendMessage={onSendMessage} isLoading={false} />);

    // select a tool via UI
    await act(async () => {
      await userEvent.click(screen.getByTitle('도구 선택'));
    });

    const priorArtItem = await screen.findByText('선행기술조사');
    await act(async () => {
      await userEvent.click(priorArtItem);
    });

    await typeAndSend('once');
    await waitFor(() => expect(onSendMessage).toHaveBeenCalledWith('once', [], 'prior-art'));

    // tool should be cleared back to "도구 선택" button
    await waitFor(() => expect(screen.getByTitle('도구 선택')).toBeInTheDocument());

    await typeAndSend('twice');
    // second call should not include tool (it is reset to null)
    await waitFor(() => expect(onSendMessage).toHaveBeenLastCalledWith('twice', [], undefined));
  });
});
