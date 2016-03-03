# Copyright 2016 - Nokia
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

from oslo_config import cfg

from vitrage.common.constants import EventAction
from vitrage.common.constants import SyncMode
from vitrage.common.constants import VertexProperties as VProps
from vitrage.entity_graph.initialization_status import InitializationStatus
from vitrage.entity_graph.processor import processor as proc
from vitrage.entity_graph.states.resource_state import NormalizedResourceState
from vitrage.synchronizer.plugins.nova.instance.transformer import \
    InstanceTransformer
from vitrage.tests.functional.entity_graph.base import \
    TestEntityGraphFunctionalBase


class TestStateManagerFunctional(TestEntityGraphFunctionalBase):

    def setUp(self):
        super(TestStateManagerFunctional, self).setUp()
        self.conf = cfg.ConfigOpts()
        self.conf.register_opts(self.PROCESSOR_OPTS, group='entity_graph')

    def test_state_on_update(self):
        # setup
        processor = proc.Processor(self.conf, InitializationStatus())
        event = self._create_event(spec_type='INSTANCE_SPEC',
                                   sync_mode=SyncMode.INIT_SNAPSHOT)

        # action
        processor.process_event(event)

        # test assertions
        instance_transformer = InstanceTransformer({})
        vitrage_id = instance_transformer.extract_key(event)
        vertex = processor.entity_graph.get_vertex(vitrage_id)
        self.assertEqual(NormalizedResourceState.RUNNING,
                         vertex[VProps.AGGREGATED_STATE])

    def test_state_on_neighbor_update(self):
        # setup
        vertex, neighbors, processor = self._create_entity(
            spec_type='INSTANCE_SPEC',
            sync_mode=SyncMode.INIT_SNAPSHOT)
        self.assertEqual(2, processor.entity_graph.num_vertices())

        neighbors[0].vertex[VProps.STATE] = 'available'
        neighbors[0].vertex[VProps.IS_PLACEHOLDER] = False

        # action
        processor._connect_neighbors(neighbors, [], EventAction.UPDATE)

        # test assertions
        neighbor_vertex = processor.entity_graph.get_vertex(
            neighbors[0].vertex.vertex_id)
        self.assertEqual(NormalizedResourceState.RUNNING,
                         neighbor_vertex[VProps.AGGREGATED_STATE])