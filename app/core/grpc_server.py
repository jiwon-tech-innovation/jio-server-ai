        Receives AudioStream, aggregates bytes, performs STT -> Chat.
        Matches Dev 1's Proto definition.
        """
        audio_buffer = bytearray()
        
        try:
            async for request in request_iterator:
                audio_buffer.extend(request.audio_data)
                if request.is_final:
                    break
        except Exception as e:
            print(f"gRPC Stream Error: {e}")

        # 1. STT
        stt_response = await stt.transcribe_bytes(bytes(audio_buffer), file_ext="mp3")
        user_text = stt_response.text

        # 2. Classify (Judgment: STUDY vs PLAY)
        # Use stt_result as content, type="TEXT" or "PROCESS_NAME" context
        classify_request = ClassifyRequest(content_type="BEHAVIOR", content=user_text)
        classify_response = await classifier.classify_content(classify_request)

        # 3. Chat (Tsundere Response)
        chat_request = ChatRequest(text=user_text)
        chat_response = await chat.chat_with_persona(chat_request)

        # 4. Construct JSON Intent
        # Combine Chat (Response, Command) + Classifier (State)
        intent_data = {
            "text": chat_response.text,
            "state": classify_response.result,  # STUDY / PLAY
            "type": chat_response.type,         # CHAT / COMMAND
            "command": chat_response.command,
            "parameter": chat_response.parameter
        }
        
        final_intent = json.dumps(intent_data, ensure_ascii=False)

        return audio_pb2.AudioResponse(
            transcript=user_text,
            is_emergency=False,
            intent=final_intent
        )

async def serve_grpc():
    server = grpc.aio.server()
    audio_pb2_grpc.add_AudioServiceServicer_to_server(AudioService(), server)
    server.add_insecure_port('[::]:50051')
    print("gRPC Server running on port 50051 (Service: AudioService)...")
    await server.start()
    await server.wait_for_termination()
