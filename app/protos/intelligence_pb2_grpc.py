# -*- coding: utf-8 -*-
"""gRPC stubs for IntelligenceService."""
import grpc

from app.protos import intelligence_pb2 as _intelligence_pb2


class IntelligenceServiceStub:
    """Client stub for IntelligenceService."""
    
    def __init__(self, channel):
        """Constructor.
        
        Args:
            channel: A grpc.Channel.
        """
        self.AnalyzeLog = channel.unary_unary(
            '/jiaa.IntelligenceService/AnalyzeLog',
            request_serializer=_intelligence_pb2.LogAnalysisRequest.SerializeToString,
            response_deserializer=_intelligence_pb2.LogAnalysisResponse.FromString,
        )
        self.ClassifyURL = channel.unary_unary(
            '/jiaa.IntelligenceService/ClassifyURL',
            request_serializer=_intelligence_pb2.URLClassifyRequest.SerializeToString,
            response_deserializer=_intelligence_pb2.URLClassifyResponse.FromString,
        )
        self.TranscribeAudio = channel.stream_unary(
            '/jiaa.IntelligenceService/TranscribeAudio',
            request_serializer=_intelligence_pb2.AudioChunk.SerializeToString,
            response_deserializer=_intelligence_pb2.TranscribeResponse.FromString,
        )


class IntelligenceServiceServicer:
    """Server servicer interface for IntelligenceService."""
    
    def AnalyzeLog(self, request, context):
        """에러 로그 분석 (Emergency Protocol)"""
        context.set_code(grpc.StatusCode.UNIMPLEMENTED)
        context.set_details('Method not implemented!')
        raise NotImplementedError('Method not implemented!')
    
    def ClassifyURL(self, request, context):
        """URL/Title 분류 (Study vs Play)"""
        context.set_code(grpc.StatusCode.UNIMPLEMENTED)
        context.set_details('Method not implemented!')
        raise NotImplementedError('Method not implemented!')
    
    def TranscribeAudio(self, request_iterator, context):
        """실시간 STT (스트리밍)"""
        context.set_code(grpc.StatusCode.UNIMPLEMENTED)
        context.set_details('Method not implemented!')
        raise NotImplementedError('Method not implemented!')


def add_IntelligenceServiceServicer_to_server(servicer, server):
    """Add IntelligenceServiceServicer to a gRPC server."""
    rpc_method_handlers = {
        'AnalyzeLog': grpc.unary_unary_rpc_method_handler(
            servicer.AnalyzeLog,
            request_deserializer=_intelligence_pb2.LogAnalysisRequest.FromString,
            response_serializer=_intelligence_pb2.LogAnalysisResponse.SerializeToString,
        ),
        'ClassifyURL': grpc.unary_unary_rpc_method_handler(
            servicer.ClassifyURL,
            request_deserializer=_intelligence_pb2.URLClassifyRequest.FromString,
            response_serializer=_intelligence_pb2.URLClassifyResponse.SerializeToString,
        ),
        'TranscribeAudio': grpc.stream_unary_rpc_method_handler(
            servicer.TranscribeAudio,
            request_deserializer=_intelligence_pb2.AudioChunk.FromString,
            response_serializer=_intelligence_pb2.TranscribeResponse.SerializeToString,
        ),
    }
    generic_handler = grpc.method_handlers_generic_handler(
        'jiaa.IntelligenceService', rpc_method_handlers)
    server.add_generic_rpc_handlers((generic_handler,))


class IntelligenceService(grpc.ServicerContext):
    """Service descriptor for reflection."""
    
    @staticmethod
    def AnalyzeLog(request, target, options=(), channel_credentials=None,
                   call_credentials=None, insecure=False, compression=None,
                   wait_for_ready=None, timeout=None, metadata=None):
        return grpc.experimental.unary_unary(request, target, '/jiaa.IntelligenceService/AnalyzeLog',
                                              _intelligence_pb2.LogAnalysisRequest.SerializeToString,
                                              _intelligence_pb2.LogAnalysisResponse.FromString,
                                              options, channel_credentials,
                                              insecure, call_credentials, compression, wait_for_ready, timeout, metadata)
    
    @staticmethod
    def ClassifyURL(request, target, options=(), channel_credentials=None,
                    call_credentials=None, insecure=False, compression=None,
                    wait_for_ready=None, timeout=None, metadata=None):
        return grpc.experimental.unary_unary(request, target, '/jiaa.IntelligenceService/ClassifyURL',
                                              _intelligence_pb2.URLClassifyRequest.SerializeToString,
                                              _intelligence_pb2.URLClassifyResponse.FromString,
                                              options, channel_credentials,
                                              insecure, call_credentials, compression, wait_for_ready, timeout, metadata)
